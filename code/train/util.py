'''
Supporting functions for use in training scripts.
'''

import cPickle as p
import numpy as np
import brian as b
import os, sys

from struct import unpack
from numpy import linalg as la
from sklearn.preprocessing import normalize

top_level_path = os.path.join('..', '..')
MNIST_data_path = os.path.join(top_level_path, 'data')
CIFAR10_data_path = os.path.join(top_level_path, 'data', 'cifar-10-batches-py')


def nearestPD(A):
    """Find the nearest positive-definite matrix to input
    A Python/Numpy port of John D'Errico's `nearestSPD` MATLAB code [1], which
    credits [2].
    [1] https://www.mathworks.com/matlabcentral/fileexchange/42885-nearestspd
    [2] N.J. Higham, "Computing a nearest symmetric positive semidefinite
    matrix" (1988): https://doi.org/10.1016/0024-3795(88)90223-6
    """

    B = (A + A.T) / 2
    _, s, V = la.svd(B)

    H = np.dot(V.T, np.dot(np.diag(s), V))

    A2 = (B + H) / 2

    A3 = (A2 + A2.T) / 2

    if isPD(A3):
        return A3

    spacing = np.spacing(la.norm(A))
    # The above is different from [1]. It appears that MATLAB's `chol` Cholesky
    # decomposition will accept matrixes with exactly 0-eigenvalue, whereas
    # Numpy's will not. So where [1] uses `eps(mineig)` (where `eps` is Matlab
    # for `np.spacing`), we use the above definition. CAVEAT: our `spacing`
    # will be much larger than [1]'s `eps(mineig)`, since `mineig` is usually on
    # the order of 1e-16, and `eps(1e-16)` is on the order of 1e-34, whereas
    # `spacing` will, for Gaussian random matrixes of small dimension, be on
    # othe order of 1e-16. In practice, both ways converge, as the unit test
    # below suggests.
    I = np.eye(A.shape[0])
    k = 1
    while not isPD(A3):
        mineig = np.min(np.real(la.eigvals(A3)))
        A3 += I * (-mineig * k**2 + spacing)
        k += 1

    return A3


def isPD(B):
    """Returns true when input is positive-definite, via Cholesky"""
    try:
        _ = la.cholesky(B)
        return True
    except la.LinAlgError:
        return False


def is_invertible(a):
	return a.shape[0] == a.shape[1] and np.linalg.matrix_rank(a) == a.shape[0]


def mhat(t, sigma=1.0, scale=1.0, shift=0.0, max_excite=np.inf, max_inhib=-np.inf):
	'''
	Truly, this is the Ricker wavelet, which is the negative normalized second derivative
	of a Gaussian function; i.e., up to scale and normalization, the second Hermite function.
	It is frequently employed to model seismic data, or is used as a broad spectrum source
	term in computational electrodynamics.

	It is only referred to as the Mexican hat wavelet in the Americas due to its taking the
	shape of a sombrero when used as a 2D image processing kernel.

	See https://en.wikipedia.org/wiki/Mexican_hat_wavelet for more details and references.
	'''
	return -np.maximum(np.minimum(scale * np.divide(2, np.sqrt(3 * \
								sigma) * (np.pi ** 0.25)) * (1.0 - \
								np.square(np.divide(t, sigma))) * \
								np.exp(-np.divide(np.square(t), 2 * \
								np.square(sigma))) + shift, max_excite), max_inhib)


def get_labeled_data(pickle_name, train=True, reduced_dataset=False, \
			classes=range(10), examples_per_class=100, normalized_inputs=False):
	'''
	Read input-vector (image) and target class (label, 0-9) and return it as 
	a list of tuples.
	'''
	if reduced_dataset:
		pickle_name = '_'.join([pickle_name, 'reduced', '_'.join([ str(class_) for \
										class_ in classes ]), str(examples_per_class)])
	elif normalized_inputs:
		pickle_name = '_'.join([pickle_name, 'normalized_inputs'])

	if os.path.isfile('%s.pickle' % pickle_name):
		data = p.load(open('%s.pickle' % pickle_name))
	else:
		# Open the images with gzip in read binary mode
		if train:
			images = open(os.path.join(MNIST_data_path, 'train-images-idx3-ubyte'), 'rb')
			labels = open(os.path.join(MNIST_data_path, 'train-labels-idx1-ubyte'), 'rb')
		else:
			images = open(os.path.join(MNIST_data_path, 't10k-images-idx3-ubyte'), 'rb')
			labels = open(os.path.join(MNIST_data_path, 't10k-labels-idx1-ubyte'), 'rb')

		# Get metadata for images
		images.read(4)  # skip the magic_number
		number_of_images = unpack('>I', images.read(4))[0]
		rows = unpack('>I', images.read(4))[0]
		cols = unpack('>I', images.read(4))[0]

		# Get metadata for labels
		labels.read(4)  # skip the magic_number
		N = unpack('>I', labels.read(4))[0]

		if number_of_images != N:
			raise Exception('number of labels did not match the number of images')

		# Get the data
		print '...Loading MNIST data from disk.'
		print '\n'

		x = np.zeros((N, rows, cols), dtype=np.uint8)  # Initialize numpy array
		y = np.zeros((N, 1), dtype=np.uint8)  # Initialize numpy array

		for i in xrange(N):
			if i % 1000 == 0:
				print 'Progress :', i, '/', N
			x[i] = [[unpack('>B', images.read(1))[0] for unused_col in xrange(cols)] for unused_row in xrange(rows) ]
			y[i] = unpack('>B', labels.read(1))[0]

		print 'Progress :', N, '/', N, '\n'

		if reduced_dataset:
			reduced_x = np.zeros((examples_per_class * len(classes), rows, cols), dtype=np.uint8)
			for idx, class_index in enumerate(classes):
				current = examples_per_class * idx
				for example_index, example in enumerate(x):
					if y[example_index] == class_index:
						reduced_x[current, :, :] = x[example_index, :, :]
						current += 1
						if current == examples_per_class * (idx + 1):
							break

			reduced_y = np.array([ label // examples_per_class for label in xrange(examples_per_class * len(classes)) ],
															dtype=np.uint8).reshape((examples_per_class * len(classes), 1))
	
			# Randomize order of data examples
			rng_state = np.random.get_state()
			np.random.shuffle(reduced_x)
			np.random.set_state(rng_state)
			np.random.shuffle(reduced_y)

			# Set data to reduced data
			x, y = reduced_x, reduced_y

		if normalized_inputs:
			x = x.reshape([x.shape[0], rows * cols])
			x = np.asarray(x, dtype=np.float64)
			x_mean = np.sum(x) / (x.shape[0])

			for i in xrange(x.shape[0]):
				x[i, :] *= x_mean / np.sum(x[i, :]) 

			x = x.reshape([x.shape[0], rows, cols])

		data = {'x': x, 'y': y, 'rows': rows, 'cols': cols}

		p.dump(data, open("%s.pickle" % pickle_name, "wb"))

	return data


def get_labeled_CIFAR10_data(train=True, single_channel=True):
	data = {}
	if train:
		files = ['data_batch_1', 'data_batch_2', 'data_batch_3', 'data_batch_4', 'data_batch_5']
	else:
		files = ['test_batch']
	
	for idx, file in enumerate(files):
		with open(os.path.join(CIFAR10_data_path, file), 'rb') as open_file:
			if idx == 0:
				data = p.load(open_file)

				del data['batch_label']
				del data['filenames']
			else:
				temp_data = p.load(open_file)

				data['data'] = np.vstack([data['data'], temp_data['data']])
				data['labels'] = np.hstack([data['labels'], temp_data['labels']])

	if single_channel:
		data['data'] = np.reshape(data['data'], (data['data'].shape[0], 3, 1024))
		data['data'] = np.mean(data['data'], axis=1)
		data['data'] = data['data'].reshape((data['data'].shape[0], 32, 32))
	else:
		data['data'] = data['data'].reshape((data['data'].shape[0], 3, 32, 32))

	return data


def is_lattice_connection(sqrt, i, j, lattice_structure):
	'''
	Boolean method which checks if two indices in a network correspond to neighboring nodes in a 4-, 8-, or all-lattice.

	n_e: Square root of the number of nodes in population
	i: First neuron's index
	k: Second neuron's index
	lattice_structure: Connectivity pattern between connected patches
	'''
	if lattice_structure == 'none':
		return False
	if lattice_structure == '4':
		return i + 1 == j and j % sqrt != 0 or i - 1 == j and i % sqrt != 0 or i + sqrt == j or i - sqrt == j
	if lattice_structure == '8':
		return i + 1 == j and j % sqrt != 0 or i - 1 == j and i % sqrt != 0 or i + sqrt == j or i - sqrt == j \
								or i + sqrt == j + 1 and j % sqrt != 0 or i + sqrt == j - 1 and i % sqrt != 0 \
								or i - sqrt == j + 1 and i % sqrt != 0 or i - sqrt == j - 1 and j % sqrt != 0
	if lattice_structure == 'all':
		return True


def get_neighbors(n, sqrt):
	i, j = n // sqrt, n % sqrt
	
	neighbors = []
	for (i_, j_) in [(i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1), (i + 1, j + 1), \
										(i + 1, j - 1), (i - 1, j + 1), (i - 1, j - 1)]:
		if is_lattice_connection(sqrt, i * sqrt + j, i_ * sqrt + j_, '8') \
					and i_ * sqrt + j_ >= 0 and i_ * sqrt + j_ < sqrt ** 2:
			neighbors.append(i_ * sqrt + j_)

	return neighbors


def get_mesh_neighbors(n, sqrt, lattice):
	i, j = n // sqrt, n % sqrt
	
	neighbors = []
	for (i_, j_) in [(i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1), (i + 1, j + 1), \
										(i + 1, j - 1), (i - 1, j + 1), (i - 1, j - 1)]:
		if is_lattice_connection(sqrt, i * sqrt + j, i_ * sqrt + j_, str(lattice)) \
					and i_ * sqrt + j_ >= 0 and i_ * sqrt + j_ < sqrt ** 2:
			neighbors.append(i_ * sqrt + j_)

	return neighbors


def save_connections(weights_dir, connections, input_connections, ending, suffix):
	'''
	Save all synaptic connection parameters out to disk.
	'''

	# merge two dictionaries of connections into one
	connections.update(input_connections)

	# save out each connection's parameters to disk
	for connection_name in connections.keys():		
		# get parameters of this connection
		if type(connections[connection_name][:]) == b.DenseConnectionMatrix:
			connection_matrix = connections[connection_name][:]
		else:
			connection_matrix = connections[connection_name][:].todense()
		# save it out to disk
		if suffix != None:
			np.save(os.path.join(weights_dir, connection_name + '_' + ending + '_' + str(suffix)), connection_matrix)
		else:
			np.save(os.path.join(weights_dir, connection_name + '_' + ending), connection_matrix)


def save_theta(weights_dir, populations, neuron_groups, ending, suffix):

	'''
	Save the adaptive threshold parameters out to disk.
	'''

	# iterate over population for which to save theta parameters
	for population in populations:
		# save out the theta parameters to file
		if suffix != None:
			np.save(os.path.join(weights_dir, 'theta_' + population + '_' + ending + '_' + str(suffix)), neuron_groups[population + 'e'].theta)
		else:
			np.save(os.path.join(weights_dir, 'theta_' + population + '_' + ending), neuron_groups[population + 'e'].theta)


def save_assignments(weights_dir, assignments, ending, suffix):
	'''
	Save neuron class labels out to disk.
	'''

	# save the labels assigned to excitatory neurons out to disk
	np.save(os.path.join(weights_dir, '_'.join(['assignments', ending, str(suffix)])), assignments)


def save_accumulated_rates(weights_dir, accumulated_rates, ending, suffix):
	'''
	Save neuron class labels out to disk.
	'''

	# save the labels assigned to excitatory neurons out to disk
	np.save(os.path.join(weights_dir, '_'.join(['accumulated_rates', ending, str(suffix)])), assignments)