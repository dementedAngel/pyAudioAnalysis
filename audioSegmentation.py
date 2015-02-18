import numpy, mlpy, time, scipy, os
import audioFeatureExtraction as aF
import audioTrainTest as aT
import audioBasicIO
import matplotlib.pyplot as plt
from scipy.spatial import distance
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from sklearn.lda import LDA

# # # # # # # # # # # # # # #
# General utility functions #
# # # # # # # # # # # # # # #

def smoothMovingAvg(inputSignal, windowLen=11):
	windowLen = int(windowLen)
	if inputSignal.ndim != 1:
		raise ValueError, ""
	if inputSignal.size < windowLen:
		raise ValueError, "Input vector needs to be bigger than window size."
	if windowLen<3:
		return inputSignal
	s = numpy.r_[2*inputSignal[0] - inputSignal[windowLen-1::-1], inputSignal, 2*inputSignal[-1]-inputSignal[-1:-windowLen:-1]]
	w = numpy.ones(windowLen, 'd')
	y = numpy.convolve(w/w.sum(), s, mode='same')
	return y[windowLen:-windowLen+1]

def selfSimilarityMatrix(featureVectors):
	'''
	This function computes the self-similarity matrix for a sequence of feature vectors.	
	ARGUMENTS:
	 - featureVectors: 	a numpy matrix (nDims x nVectors) whose i-th column corresponds to the i-th feature vector
	
	RETURNS:
	 - S:		 	the self-similarity matrix (nVectors x nVectors)
	'''

	[nDims, nVectors] = featureVectors.shape
	[featureVectors2, MEAN, STD] = aT.normalizeFeatures([featureVectors.T])
	featureVectors2 = featureVectors2[0].T
	S = 1.0 - distance.squareform(distance.pdist(featureVectors2.T, 'cosine'))
	return S

def flags2segs(Flags, window):
	'''
	ARGUMENTS:
	 - Flags: 	a sequence of class flags (per time window)
	 - window:	window duration (in seconds)
	
	RETURNS:
	 - segs:	a sequence of segment's endpoints: segs[i] is the endpoint of the i-th segment (in seconds)
	 - classes:	a sequence of class flags: class[i] is the class ID of the i-th segment
	'''

	preFlag = 0
	curFlag = 0
	numOfSegments = 0

	curVal = Flags[curFlag]
	segs = []
	classes = []
	while (curFlag<len(Flags)-1):
		stop = 0
	 	preFlag = curFlag
		preVal = curVal
	 	while (stop==0):
			curFlag = curFlag + 1
			tempVal = Flags[curFlag]
			if ((tempVal != curVal) | (curFlag==len(Flags)-1)): # stop
				numOfSegments = numOfSegments + 1
				stop = 1
				curSegment = curVal
				curVal = Flags[curFlag]
				segs.append((curFlag*window))
				classes.append(preVal)
	return (segs, classes)

def mtFileClassification(inputFile, modelName, modelType, plotResults = False):
	'''
	This function performs mid-term classification of an audio stream.
	Towards this end, supervised knowledge is used, i.e. a pre-trained classifier.
	ARGUMENTS:
		- inputFile:		path of the input WAV file
		- modelName:		name of the classification model
		- modelType:		svm or knn depending on the classifier type
		- plotResults:		True if results are to be plotted using matplotlib along with a set of statistics
	
	RETURNS:
	  	- segs:			a sequence of segment's endpoints: segs[i] is the endpoint of the i-th segment (in seconds)
		- classes:		a sequence of class flags: class[i] is the class ID of the i-th segment
	'''

	if not os.path.isfile(modelName):
		print "mtFileClassificationError: input modelType not found!"
		return (-1,-1)

	# Load classifier:
	if modelType=='svm':
		[Classifier, MEAN, STD, classNames, mtWin, mtStep, stWin, stStep, computeBEAT] = aT.loadSVModel(modelName)
	elif modelType=='knn':
		[Classifier, MEAN, STD, classNames, mtWin, mtStep, stWin, stStep, computeBEAT] = aT.loadKNNModel(modelName)
	if computeBEAT:
		print "Model " + modelName + " contains long-term music features (beat etc) and cannot be used in segmentation"	
		return (-1,-1)
	[Fs, x] = audioBasicIO.readAudioFile(inputFile)		# load input file
	if Fs == -1:						# could not read file
		return  (-1,-1)
	x = audioBasicIO.stereo2mono(x);					# convert stereo (if) to mono
	Duration = len(x) / Fs					
								# mid-term feature extraction:
	[MidTermFeatures, _] = aF.mtFeatureExtraction(x, Fs, mtWin * Fs, mtStep * Fs, round(Fs*stWin), round(Fs*stStep));
	flags = []; Ps = []; flagsInd = []
	for i in range(MidTermFeatures.shape[1]): 		# for each feature vector (i.e. for each fix-sized segment):
		curFV = (MidTermFeatures[:, i] - MEAN) / STD;	# normalize current feature vector					
		[Result, P] = aT.classifierWrapper(Classifier, modelType, curFV)	# classify vector
		flagsInd.append(Result)
		flags.append(classNames[int(Result)])		# update class label matrix
		Ps.append(numpy.max(P))				# update probability matrix

	(segs, classes) = flags2segs(flags, mtStep)		# convert fix-sized flags to segments and classes
	segs[-1] = len(x) / float(Fs)

	if plotResults:
		for i in range(len(classes)):
			if i==0:
				print "{0:3.1f} -- {1:3.1f} : {2:20s}".format(0.0, segs[i], classes[i])
			else:
				print "{0:3.1f} -- {1:3.1f} : {2:20s}".format(segs[i-1], segs[i], classes[i])

		# # # # # # # # # # # # 
		# Generate Statistics #
		# # # # # # # # # # # # 
		SPercentages = numpy.zeros((len(classNames), 1))
		Percentages = numpy.zeros((len(classNames), 1))
		AvDurations   = numpy.zeros((len(classNames), 1))

		for iSeg in range(len(segs)):
			if iSeg==0:
				SPercentages[classNames.index(classes[iSeg])] += (segs[iSeg])
			else:
				SPercentages[classNames.index(classes[iSeg])] += (segs[iSeg]-segs[iSeg-1])

		for i in range(SPercentages.shape[0]):
			Percentages[i] = 100.0*SPercentages[i] / Duration
			S = sum(1 for c in classes if c==classNames[i])
			if S>0:
				AvDurations[i] = SPercentages[i] / S
			else:
				AvDurations[i] = 0.0

		for i in range(Percentages.shape[0]):
			print classNames[i], Percentages[i], AvDurations[i]

		font = {'family' : 'fantasy', 'size'   : 10}
		plt.rc('font', **font)

		fig = plt.figure()	
		ax1 = fig.add_subplot(211)
		ax1.set_yticks(numpy.array(range(len(classNames))))
		ax1.axis((0, Duration, -1, len(classNames)))
		ax1.set_yticklabels(classNames)
		ax1.plot(numpy.array(range(len(flags)))*mtStep+mtStep/2.0, flagsInd)
		plt.xlabel("time (seconds)")

		ax2 = fig.add_subplot(223)
		plt.title("Classes percentage durations")
		ax2.axis((0, len(classNames)+1, 0, 100))
		ax2.set_xticks(numpy.array(range(len(classNames)+1)))
		ax2.set_xticklabels([" "] + classNames)
		ax2.bar(numpy.array(range(len(classNames)))+0.5, Percentages)

		ax3 = fig.add_subplot(224)
		plt.title("Segment average duration per class")
		ax3.axis((0, len(classNames)+1, 0, AvDurations.max()))
		ax3.set_xticks(numpy.array(range(len(classNames)+1)))
		ax3.set_xticklabels([" "] + classNames)
		ax3.bar(numpy.array(range(len(classNames)))+0.5, AvDurations)
		fig.tight_layout()
		plt.show()
	return (segs, classes)

def silenceRemoval(x, Fs, stWin, stStep, smoothWindow = 0.5, Weight = 0.5, plot = False):
	'''
	Event Detection (silence removal)
	ARGUMENTS:
		 - x:			the input audio signal
		 - Fs:			sampling freq
		 - stWin, stStep:	window size and step in seconds
		 - smoothWindow:	(optinal) smooth window (in seconds)
		 - Weight:		(optinal) weight factor (0 < Weight < 1) the higher, the more strict
		 - plot:		(optinal) True if results are to be plotted
	RETURNS:
		 - segmentLimits:	list of segment limits in seconds (e.g [[0.1, 0.9], [1.4, 3.0]] means that 
					the resulting segments are (0.1 - 0.9) seconds and (1.4, 3.0) seconds 
	'''

	if Weight>=1:
		Weight = 0.99;
	if Weight<=0:
		Weight = 0.01;

	# Step 1: feature extraction
	x = audioBasicIO.stereo2mono(x);						# convert to mono
	ShortTermFeatures = aF.stFeatureExtraction(x, Fs, stWin*Fs, stStep*Fs)		# extract short-term features	

	# Step 2: train binary SVM classifier of low vs high energy frames
	EnergySt = ShortTermFeatures[1, :]						# keep only the energy short-term sequence (2nd feature)
	E = numpy.sort(EnergySt)							# sort the energy feature values:
	L1 = int(len(E)/10)								# number of 10% of the total short-term windows
	T1 = numpy.mean(E[0:L1])							# compute "lower" 10% energy threshold 
	T2 = numpy.mean(E[-L1:-1])							# compute "higher" 10% energy threshold
	Class1 = ShortTermFeatures[:,numpy.where(EnergySt<T1)[0]]			# get all features that correspond to low energy
	Class2 = ShortTermFeatures[:,numpy.where(EnergySt>T2)[0]]			# get all features that correspond to high energy
	featuresSS = [Class1.T, Class2.T];						# form the binary classification task and ...
	[featuresNormSS, MEANSS, STDSS] = aT.normalizeFeatures(featuresSS)		# normalize and ...
	SVM = aT.trainSVM(featuresNormSS, 1.0)						# train the respective SVM probabilistic model (ONSET vs SILENCE)

	# Step 3: compute onset probability based on the trained SVM
	ProbOnset = []
	for i in range(ShortTermFeatures.shape[1]):					# for each frame
		curFV = (ShortTermFeatures[:,i] - MEANSS) / STDSS			# normalize feature vector
		ProbOnset.append(SVM.pred_probability(curFV)[1])			# get SVM probability (that it belongs to the ONSET class)
	ProbOnset = numpy.array(ProbOnset)
	ProbOnset = smoothMovingAvg(ProbOnset, smoothWindow / stStep)			# smooth probability

	# Step 4A: detect onset frame indices:
	ProbOnsetSorted = numpy.sort(ProbOnset)						# find probability Threshold as a weighted average of top 10% and lower 10% of the values
	Nt = ProbOnsetSorted.shape[0] / 10;
	print Weight
	T = (numpy.mean( (1-Weight)*ProbOnsetSorted[0:Nt] ) + Weight*numpy.mean(ProbOnsetSorted[-Nt::]) )
	print T

	MaxIdx = numpy.where(ProbOnset>T)[0];						# get the indices of the frames that satisfy the thresholding
	i = 0;
	timeClusters = []
	segmentLimits = []

	# Step 4B: group frame indices to onset segments
	while i<len(MaxIdx):								# for each of the detected onset indices
		curCluster = [MaxIdx[i]]
		if i==len(MaxIdx)-1:
			break		
		while MaxIdx[i+1] - curCluster[-1] <= 2:
			curCluster.append(MaxIdx[i+1])
			i += 1
			if i==len(MaxIdx)-1:
				break
		i += 1
		timeClusters.append(curCluster)
		segmentLimits.append([curCluster[0]*stStep, curCluster[-1]*stStep])

	# Step 5: Post process: remove very small segments:
	minDuration = 0.2;
	segmentLimits2 = []
	for s in segmentLimits:
		if s[1] - s[0] > minDuration:
			segmentLimits2.append(s)
	segmentLimits = segmentLimits2;

	if plot:
		timeX = numpy.arange(0, x.shape[0] / float(Fs) , 1.0/Fs)

		plt.subplot(2,1,1); plt.plot(timeX, x)
		for s in segmentLimits:
			plt.axvline(x=s[0]); 
			plt.axvline(x=s[1]); 
		plt.subplot(2,1,2); plt.plot(numpy.arange(0, ProbOnset.shape[0] * stStep, stStep), ProbOnset);
		plt.title('Signal')
		for s in segmentLimits:
			plt.axvline(x=s[0]); 
			plt.axvline(x=s[1]); 
		plt.title('SVM Probability')
		plt.show()

	return segmentLimits


def speakerDiarization(x, Fs, mtSize, mtStep, numOfSpeakers):
	x = audioBasicIO.stereo2mono(x);
	Duration = len(x) / Fs
	[MidTermFeatures, ShortTermFeatures] = aF.mtFeatureExtraction(x, Fs, mtSize * Fs, mtStep * Fs, round(Fs*0.040), round(Fs*0.020));
	(MidTermFeaturesNorm, MEAN, STD) = aT.normalizeFeatures([MidTermFeatures.T])
	MidTermFeaturesNorm = MidTermFeaturesNorm[0].T

	numOfWindows = MidTermFeatures.shape[1]

	# remove outliers:
	DistancesAll = numpy.sum(distance.squareform(distance.pdist(MidTermFeaturesNorm.T)), axis=0)
	MDistancesAll = numpy.mean(DistancesAll)
	iNonOutLiers = numpy.nonzero(DistancesAll < 2.0*MDistancesAll)[0]
	perOutLier = (100.0*(numOfWindows-iNonOutLiers.shape[0])) / numOfWindows
	print "{0:3.1f}% of the initial feature vectors are outlier".format(perOutLier)
	MidTermFeaturesNorm = MidTermFeaturesNorm[:, iNonOutLiers]

	# TODO: dimensionality reduction here

	"""
	[mtFeaturesToReduce, _] = aF.mtFeatureExtraction(x, Fs, mtSize * Fs, 0.020 * Fs, round(Fs*0.040), round(Fs*0.020));
	(mtFeaturesToReduce, MEAN, STD) = aT.normalizeFeatures([mtFeaturesToReduce.T])
	mtFeaturesToReduce = mtFeaturesToReduce[0].T
	DistancesAll = numpy.sum(distance.squareform(distance.pdist(mtFeaturesToReduce.T)), axis=0)
	MDistancesAll = numpy.mean(DistancesAll)
	iNonOutLiers2 = numpy.nonzero(DistancesAll < 2.0*MDistancesAll)[0]
	mtFeaturesToReduce = mtFeaturesToReduce[:, iNonOutLiers2]
	Labels = numpy.zeros((mtFeaturesToReduce.shape[1],));
	for i in range(Labels.shape[0]):
		Labels[i] = int(i/50);
	clf = LDA(n_components=5)
	clf.fit(mtFeaturesToReduce.T, Labels)	
	MidTermFeaturesNorm = (clf.transform(MidTermFeaturesNorm.T)).T
	"""

	"""
	[mtFeaturesToReduce, _] = aF.mtFeatureExtraction(x, Fs, mtSize * Fs, 0.020 * Fs, round(Fs*0.040), round(Fs*0.020));
	(mtFeaturesToReduce, MEAN, STD) = aT.normalizeFeatures([mtFeaturesToReduce.T])
	mtFeaturesToReduce = mtFeaturesToReduce[0].T
	DistancesAll = numpy.sum(distance.squareform(distance.pdist(mtFeaturesToReduce.T)), axis=0)
	MDistancesAll = numpy.mean(DistancesAll)
	iNonOutLiers2 = numpy.nonzero(DistancesAll < 2.0*MDistancesAll)[0]
	print mtFeaturesToReduce.shape
	mtFeaturesToReduce = mtFeaturesToReduce[:, iNonOutLiers2]
	print mtFeaturesToReduce.shape

	Labels = numpy.zeros((mtFeaturesToReduce.shape[1],));
	for i in range(Labels.shape[0]):
		Labels[i] = int(i/10);
	
	_, w = aT.lda(mtFeaturesToReduce.T,Labels.T, 20)
	MidTermFeaturesNorm = numpy.dot(w.T, MidTermFeaturesNorm)
	"""
	##



	if numOfSpeakers<=0:
		sRange = range(2,10)
	else:
		sRange = [numOfSpeakers]
	clsAll = []
	silAll = []

#	MidTermFeaturesNorm = numpy.dot(numpy.random.rand(2, MidTermFeaturesNorm.shape[0]),  MidTermFeaturesNorm)
#	print MidTermFeaturesNorm
	for iSpeakers in sRange:
		cls, means, steps = mlpy.kmeans(MidTermFeaturesNorm.T, k=iSpeakers, plus=True)		# perform k-means clustering
		# Y = distance.squareform(distance.pdist(MidTermFeaturesNorm.T))
		clsAll.append(cls)
		silA = []; silB = []
		for c in range(iSpeakers):								# for each speaker (i.e. for each extracted cluster)
			clusterPerCent = numpy.nonzero(cls==c)[0].shape[0] / float(len(cls))
			if clusterPerCent < 0.010:
				silA.append(0.0)
				silB.append(0.0)
			else:
				MidTermFeaturesNormTemp = MidTermFeaturesNorm[:,cls==c]				# get subset of feature vectors
				Yt = distance.pdist(MidTermFeaturesNormTemp.T)					# compute average distance between samples that belong to the cluster (a values)
				silA.append(numpy.mean(Yt)*clusterPerCent)
				silBs = []
				for c2 in range(iSpeakers):							# compute distances from samples of other clusters
					if c2!=c:
						clusterPerCent2 = numpy.nonzero(cls==c2)[0].shape[0] / float(len(cls))
						MidTermFeaturesNormTemp2 = MidTermFeaturesNorm[:,cls==c2]
						Yt = distance.cdist(MidTermFeaturesNormTemp.T, MidTermFeaturesNormTemp2.T)
						silBs.append(numpy.mean(Yt)*(clusterPerCent+clusterPerCent2)/2.0)
				silBs = numpy.array(silBs)							
				silB.append(min(silBs))								# ... and keep the minimum value (i.e. the distance from the "nearest" cluster)
		silA = numpy.array(silA); 
		silB = numpy.array(silB); 
		sil = []
		for c in range(iSpeakers):								# for each cluster (speaker)
			sil.append( ( silB[c] - silA[c]) / (max(silB[c],  silA[c])+0.00001)  )		# compute silhouette

		silAll.append(numpy.mean(sil))								# keep the AVERAGE SILLOUETTE

	imax = numpy.argmax(silAll)									# position of the maximum sillouette value
	nSpeakersFinal = sRange[imax]									# optimal number of clusters

	# generate the final set of cluster labels
	# (important: need to retrieve the outlier windows: this is achieved by giving them the value of their nearest non-outlier window)
	cls = numpy.zeros((numOfWindows,1))
	for i in range(numOfWindows):
		j = numpy.argmin(numpy.abs(i-iNonOutLiers))
		cls[i] = clsAll[imax][j]
	sil = silAll[imax]										# final sillouette
	classNames = ["speaker{0:d}".format(c) for c in range(nSpeakersFinal)];
	fig = plt.figure()	
	if numOfSpeakers>0:
		ax1 = fig.add_subplot(111)
	else:
		ax1 = fig.add_subplot(211)
	ax1.set_yticks(numpy.array(range(len(classNames))))
	ax1.axis((0, Duration, -1, len(classNames)))
	ax1.set_yticklabels(classNames)
	ax1.plot(numpy.array(range(len(cls)))*mtStep+mtStep/2.0, cls)
	plt.xlabel("time (seconds)")
	print sRange, silAll	
	if numOfSpeakers<=0:
		plt.subplot(212)
		plt.plot(sRange, silAll)
		plt.xlabel("number of clusters");
		plt.ylabel("average clustering's sillouette");
	plt.show()


def musicThumbnailing(x, Fs, shortTermSize=1.0, shortTermStep=0.5, thumbnailSize=10.0):
	'''
	This function detects instances of the most representative part of a music recording, also called "music thumbnails".
	A technique similar to the one proposed in [1], however a wider set of audio features is used instead of chroma features.
	In particular the following steps are followed:
	 - Extract short-term audio features. Typical short-term window size: 1 second
	 - Compute the self-silimarity matrix, i.e. all pairwise similarities between feature vectors
 	 - Apply a diagonal mask is as a moving average filter on the values of the self-similarty matrix. 
	   The size of the mask is equal to the desirable thumbnail length.
 	 - Find the position of the maximum value of the new (filtered) self-similarity matrix.
	   The audio segments that correspond to the diagonial around that position are the selected thumbnails
	

	ARGUMENTS:
	 - x:			input signal
	 - Fs:			sampling frequency
	 - shortTermSize: 	window size (in seconds)
	 - shortTermStep:	window step (in seconds)
	 - thumbnailSize:	desider thumbnail size (in seconds)
	
	RETURNS:
	 - A1:			beginning of 1st thumbnail (in seconds)
	 - A2:			ending of 1st thumbnail (in seconds)
	 - B1:			beginning of 2nd thumbnail (in seconds)
	 - B2:			ending of 2nd thumbnail (in seconds)

	USAGE EXAMPLE:
  	 import audioFeatureExtraction as aF
	 [Fs, x] = basicIO.readAudioFile(inputFile)
	 [A1, A2, B1, B2] = musicThumbnailing(x, Fs)

	[1] Bartsch, M. A., & Wakefield, G. H. (2005). Audio thumbnailing of popular music using chroma-based representations. 
	Multimedia, IEEE Transactions on, 7(1), 96-104.
	'''
	x = audioBasicIO.stereo2mono(x);
	# feature extraction:
	stFeatures = aF.stFeatureExtraction(x, Fs, Fs*shortTermSize, Fs*shortTermStep)

	# self-similarity matrix
	S = selfSimilarityMatrix(stFeatures)

	# moving filter:
	M = int(round(thumbnailSize / shortTermStep))
	B = numpy.eye(M,M)
	S = scipy.signal.convolve2d(S, B, 'valid')


	# post-processing (remove main diagonal elements)
	MIN = numpy.min(S)
	for i in range(S.shape[0]):
		for j in range(S.shape[1]):
			if abs(i-j) < 5.0 / shortTermStep or i > j:
				S[i,j] = MIN;

	# find max position:
	maxVal = numpy.max(S)
	I = numpy.argmax(S)
	[I, J] = numpy.unravel_index(S.argmax(), S.shape)

	# expand:
	i1 = I; i2 = I
	j1 = J; j2 = J

	while i2-i1<M:
		if S[i1-1, j1-1] > S[i2+1,j2+1]:
			i1 -= 1
			j1 -= 1
		else:
			i2 += 1
			j2 += 1


	return (shortTermStep*i1, shortTermStep*i2, shortTermStep*j1, shortTermStep*j2, S)

