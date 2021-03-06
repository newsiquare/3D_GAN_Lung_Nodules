# -*- coding: utf-8 -*-
"""
Created on Tue Aug  1 10:01:50 2017

@author: SMAHESH
"""

from sklearn.model_selection import RandomizedSearchCV
import tensorflow as tf
sess = tf.Session()

import os
import sys
from numpy.random import uniform
import keras
from keras.models import Sequential
from keras.wrappers.scikit_learn import KerasClassifier
from keras.layers import Dense, Dropout, Flatten
from keras.layers import Conv3D, MaxPooling3D, BatchNormalization
from keras.optimizers import Adam
from keras import backend as K
from sklearn.model_selection import StratifiedKFold
from sklearn.model_selection import cross_val_score
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
K.set_session(sess)
import time
start_time = time.time()
print("--- %s seconds ---" % (time.time() - start_time))

import shutil

import pickle
import gc
import pandas as pd
from collections import OrderedDict
import numpy as np
import random
random.seed(10)

start_time = time.time()
print("--- %s seconds ---" % (time.time() - start_time))

Xsize = 40
Ysize = 40
Zsize = 18

XYstride = 20
Zstride = 9


thresholds = [x/50.0 for x in list(range(1, 50))]
thresholds.extend([x/1000.0 for x in list(range(991, 1000))])
thresholds.extend([x/10000.0 for x in list(range(9991, 10000))])
thresholds.extend([x/100000.0 for x in list(range(99991, 100000))])
thresholds.extend([x/1000000.0 for x in list(range(999991, 1000000))])

savepath = '/home/cc/Data/'
noduleBoxes = None #this is a disctionary of all the boxes that intersect with real
with open(savepath+"noduleBoxes.pickle", "rb") as f:
    noduleBoxes = pickle.load(f)
fakeNoduleBoxes = None
with open(savepath+"fakeNoduleBoxes.pickle", "rb") as f:
    fakeNoduleBoxes = pickle.load(f)
sliceList = None
with open(savepath+"sliceamount.pickle", "rb") as f:
    sliceList = pickle.load(f)    
valSeries = None
with open(savepath+"workingValidationSeries.pickle", "rb") as f:
    valSeries = pickle.load(f)
numScans = len(valSeries)

experiment_name = sys.argv[1]  #the name of this experiment. used to name files
experiment_dir = '/home/cc/deep_learning_reu/our_models/saved_models/'+experiment_name+'/'#the directory where the experiment and it's results will be saved
records_dir = experiment_dir+'records/' #this directory contains all the code necessary that was run in the experiment
shutil.copyfile(sys.argv[0],records_dir+experiment_name+'_wholescanapp.py')
root_trials_dir = experiment_dir+'trials/' #this directory contains directories for each trial in the experiment

# make dictionary for each trial to keep track of things
experimentDict = {}
files = os.listdir(root_trials_dir)
for modelfile in files:
    trialFolder = root_trials_dir + modelfile + '/'
    modelx = keras.models.load_model(trialFolder + 'classifier_model.h5')
    print(trialFolder)

    experimentDict[modelfile] = {}
    experimentDict[modelfile]['modelx'] = modelx
    # experimentDict[modelfile]['FPrates'] = []
    # experimentDict[modelfile]['sensitivities'] = []
    # experimentDict[modelfile]['fakeSensitivities'] = []
    experimentDict[modelfile]['sumofFPs'] = np.zeros(len(thresholds))
    experimentDict[modelfile]['sumofTPs'] = np.zeros(len(thresholds))
    experimentDict[modelfile]['numDetected'] = np.zeros(len(thresholds))
    experimentDict[modelfile]['numFakesDetected'] = np.zeros(len(thresholds))
    # experimentDict[modelfile]['numNodules'] = 0
    # experimentDict[modelfile]['numFakes'] = 0

# setup the boxes
Xlow = 0
allboxXs = []
allboxYs = []
Xhigh = Xsize
while Xhigh < 512:
    allboxXs.append([Xlow, Xhigh])
    allboxYs.append([Xlow, Xhigh])
    Xlow += XYstride
    Xhigh += XYstride
counterx = 0
k = 0
numNodules = 0 #numNodules is the total number of nodules that exist across all scans
numFakes = 0 #numFakes is the total number of nodules across all scans that 1-2 radiologists agreed on

for seriesID in valSeries:
    # get the validation file
    inputs = np.array(pickle.load(open(savepath + "ValClipped" + seriesID + ".pickle", 'rb')))
    inputs = inputs.reshape(inputs.shape[0], Xsize, Ysize, Zsize, 1)
    # save numnodules and numfakes for later
    numNodules += len(noduleBoxes[seriesID])
    numFakes += len(fakeNoduleBoxes[seriesID])
    # print out for progress
    counterx+=1
    print("File: " + str(counterx))
    # make the z box
    Zlow = 0
    Zhigh = Zsize
    allboxZs = []
    coords = []
    numSlices = sliceList[k]
    k += 1
    while Zhigh < numSlices:
        allboxZs.append([Zlow, Zhigh])
        Zlow += Zstride
        Zhigh += Zstride
    allboxZs.append([numSlices - Zsize, numSlices])
    for boxZ in allboxZs:
        for boxY in allboxYs:
            for boxX in allboxXs:
                coords.append([boxX, boxY, boxZ])
    # iterate through each trial and test on this validation seriesid
    for modelfile in files:
        predictions = experimentDict[modelfile]['modelx'].predict(inputs, batch_size=48)

        nodulesFound = set()
        fakeNodulesFound = set()
        thresholds = np.sort(thresholds)
        # thresholds = reversed(thresholds) # must reverse thresholds in order to avoid rebuilding nodulesFound

        fpArr = np.zeros(len(thresholds))
        tpArr = np.zeros(len(thresholds))
        nodulesFoundArr = np.zeros(len(thresholds))
        fakeNodulesFoundArr = np.zeros(len(thresholds))

        for i in range(len(predictions)):
            # find the index of the first threshold that is greater than the prediction
            # the program predicts that a nodule exists at all thresholds below that
            threshold_index = thresholds.searchsorted(predictions[i][0], side='right')
            if threshold_index > 0:
                FP = True
                TP = False
                for node in noduleBoxes[seriesID]:
                    if coords[i] in noduleBoxes[seriesID][node]:
                        if not node in nodulesFound:
                            nodulesFound.add(node)
                            nodulesFoundArr[:threshold_index] += 1
                        FP = False
                        TP = True
                for node in fakeNoduleBoxes[seriesID]:
                    if coords[i] in fakeNoduleBoxes[seriesID][node]:
                        if not node in fakeNodulesFound:
                            fakeNodulesFound.add(node)
                            fakeNodulesFoundArr[:threshold_index] += 1
                        FP = False
                if FP:
                    fpArr[:threshold_index] += 1
                if TP:
                    tpArr[:threshold_index] += 1
        experimentDict[modelfile]['numDetected'] += nodulesFoundArr
        experimentDict[modelfile]['numFakesDetected'] += fakeNodulesFoundArr
        experimentDict[modelfile]['sumofFPs'] += fpArr
        experimentDict[modelfile]['sumofTPs'] += tpArr

# post process the data
for modelfile in files:
    trialFolder = root_trials_dir + modelfile + '/'

    sensitivities = [(x * 1.0) / numNodules for x in experimentDict[modelfile]['numDetected']]
    FPrates = [(x * 1.0) / numScans for x in experimentDict[modelfile]['sumofFPs']]
    FPratesAdj = [(a / (c+1e-10)) * b / numScans for a, b, c in zip(experimentDict[modelfile]['numDetected'], experimentDict[modelfile]['sumofFPs'], experimentDict[modelfile]['sumofTPs'])]
    fakeSensitivities = [((a + b) * 1.0) / (numNodules + numFakes) for a, b in zip(experimentDict[modelfile]['numDetected'], experimentDict[modelfile]['numFakesDetected'])]

    with open(trialFolder + "aug_sensitivities1.pickle", 'wb') as handle:
        pickle.dump(sensitivities, handle, protocol=pickle.HIGHEST_PROTOCOL)
    with open(trialFolder + "aug_FPrates1.pickle", 'wb') as handle:
        pickle.dump(FPrates, handle, protocol=pickle.HIGHEST_PROTOCOL)
    with open(trialFolder + "aug_FPratesAdj1.pickle", 'wb') as handle:
        pickle.dump(FPratesAdj, handle, protocol=pickle.HIGHEST_PROTOCOL)
    with open(trialFolder + "aug_fakeSensitivities1.pickle", 'wb') as handle:
        pickle.dump(fakeSensitivities, handle, protocol=pickle.HIGHEST_PROTOCOL)
    with open(trialFolder + "aug_sumofTPs1.pickle", 'wb') as handle:
        pickle.dump(experimentDict[modelfile]['sumofTPs'], handle, protocol=pickle.HIGHEST_PROTOCOL)
    with open(trialFolder + "aug_sumofFPs1.pickle", 'wb') as handle:
        pickle.dump(experimentDict[modelfile]['sumofFPs'], handle, protocol=pickle.HIGHEST_PROTOCOL)
    with open(trialFolder + "aug_numDetected1.pickle", 'wb') as handle:
        pickle.dump(experimentDict[modelfile]['numDetected'], handle, protocol=pickle.HIGHEST_PROTOCOL)
    with open(trialFolder + "aug_numFakesDetected1.pickle", 'wb') as handle:
        pickle.dump(experimentDict[modelfile]['numFakesDetected'], handle, protocol=pickle.HIGHEST_PROTOCOL)
    # plot line graph of FPrates vs sensitivities
    # idk if this will actually work, it's modified from a stack overflow post

    plt.gcf().clear()
    plt.plot(FPrates, sensitivities)
    plt.xlabel('FPs per Scan', fontsize=16)
    plt.ylabel("% Nodules Detected", fontsize=16)
    plt.title("FROC Curve, Certain Nodules", fontsize=24)
    plt.ylim([0, 1])
    plt.tick_params(labelsize=12)
    plt.savefig(trialFolder + 'aug_FROC_plot1.png')

    plt.gcf().clear()
    plt.plot(FPratesAdj, sensitivities)
    plt.xlabel('FPs per Scan, Adjusted', fontsize=16)
    plt.ylabel("% Nodules Detected", fontsize=16)
    plt.title("FROC Curve, Certain Nodules", fontsize=24)
    plt.ylim([0, 1])
    plt.tick_params(labelsize=12)
    plt.savefig(trialFolder + 'aug_FROC_plotAdj1.png')

    plt.gcf().clear()
    plt.plot(FPrates, fakeSensitivities)
    plt.xlabel('FPs per Scan', fontsize=16)
    plt.ylabel("% Nodules Detected", fontsize=16)
    plt.title("FROC Curve, All Nodules", fontsize=24)
    plt.ylim([0, 1])
    plt.tick_params(labelsize=12)
    plt.savefig(trialFolder + 'aug_FROC_plot21.png')

# for modelfile in os.listdir(root_trials_dir):
    #print (modelfile)
    # modelfile = '/home/cc/deep_learning_reu/our_models/saved_models/classifier_model_500-aug.h5'
    # trialFolder = root_trials_dir + modelfile + '/'
    # modelx = keras.models.load_model(trialFolder+'classifier_model.h5')
    # print(trialFolder)

    # FPrates = []
    # sensitivities = []
    # fakeSensitivities = []
    # sumofFPs = []
    # sumofTPs = []
    # numDetected = []
    # numFakesDetected = []
    # for o in range(len(thresholds)):
    #     sumofFPs.append(0)
    #     sumofTPs.append(0)
    #     numDetected.append(0)
    #     numFakesDetected.append(0)
    # k = 0
    # numNodules = 0
    # numFakes = 0

    # Xlow = 0
    # allboxXs = []
    # allboxYs = []
    # Xhigh = Xsize
    # while Xhigh < 512:
    #     allboxXs.append([Xlow, Xhigh])
    #     allboxYs.append([Xlow, Xhigh])
    #     Xlow += XYstride
    #     Xhigh += XYstride
    # counterx = 0
    # for seriesID in valSeries:
    #     counterx += 1
    #     print ("File: " + str(counterx))
    #     predictions = modelx.predict(inputs, batch_size=48)
    #
    #     Zlow = 0
    #     Zhigh = Zsize
    #     allboxZs = []
    #     coords = []
    #     numSlices = sliceList[k]
    #     k += 1
    #
    #     while Zhigh < numSlices:
    #         allboxZs.append([Zlow, Zhigh])
    #         Zlow += Zstride
    #         Zhigh += Zstride
    #     allboxZs.append([numSlices - Zsize, numSlices])
    #     for boxZ in allboxZs:
    #             for boxY in allboxYs:
    #                 for boxX in allboxXs:
    #                     coords.append([boxX, boxY, boxZ])
    #
    #     for num in range(len(thresholds)):
    #         FPs = 0
    #         TPs = 0
    #         nodulesFound = set()
    #         fakeNodulesFound = set()
    #         for i in range(len(predictions)):
    #             if predictions[i][0] >= thresholds[num]:
    #                 detection = coords[i]
    #                 FP = True
    #                 TP = False
    #                 for node in noduleBoxes[seriesID]:
    #                     if detection in noduleBoxes[seriesID][node]:
    #                         nodulesFound.add(node)
    #                         FP = False
    #                         TP = True
    #                 for node in fakeNoduleBoxes[seriesID]:
    #                     if detection in fakeNoduleBoxes[seriesID][node]:
    #                         fakeNodulesFound.add(node)
    #                         FP = False
    #                 if FP:
    #                     FPs += 1
    #                 if TP:
    #                     TPs += 1
    #         numDetected[num] += len(nodulesFound)
    #         numFakesDetected[num] += len(fakeNodulesFound)
    #         sumofFPs[num] += FPs
    #         sumofTPs[num] += TPs
    #
    #     numNodules += len(noduleBoxes[seriesID])
    #     numFakes += len(fakeNoduleBoxes[seriesID])
    #
    # sensitivities = [(x*1.0)/numNodules for x in numDetected]
    # FPrates = [(x*1.0)/numScans for x in sumofFPs]
    # FPratesAdj = [(a / c) * b / numScans for a, b, c in zip(numDetected, sumofFPs, sumofTPs)]
    # fakeSensitivities = [((a + b) * 1.0) / (numNodules + numFakes) for a, b in zip(numDetected, numFakesDetected)]
    #
    #
    # with open(trialFolder+"aug_sensitivities1.pickle", 'wb') as handle:
    #     pickle.dump(sensitivities, handle, protocol=pickle.HIGHEST_PROTOCOL)
    # with open(trialFolder+"aug_FPrates1.pickle", 'wb') as handle:
    #     pickle.dump(FPrates, handle, protocol=pickle.HIGHEST_PROTOCOL)
    # with open(trialFolder+"aug_FPratesAdj1.pickle", 'wb') as handle:
    #     pickle.dump(FPratesAdj, handle, protocol=pickle.HIGHEST_PROTOCOL)
    # with open(trialFolder+"aug_fakeSensitivities1.pickle", 'wb') as handle:
    #     pickle.dump(fakeSensitivities, handle, protocol=pickle.HIGHEST_PROTOCOL)
    # with open(trialFolder+"aug_sumofTPs1.pickle", 'wb') as handle:
    #     pickle.dump(sumofTPs, handle, protocol=pickle.HIGHEST_PROTOCOL)
    # with open(trialFolder+"aug_sumofFPs1.pickle", 'wb') as handle:
    #     pickle.dump(sumofFPs, handle, protocol=pickle.HIGHEST_PROTOCOL)
    # with open(trialFolder+"aug_numDetected1.pickle", 'wb') as handle:
    #     pickle.dump(numDetected, handle, protocol=pickle.HIGHEST_PROTOCOL)
    # with open(trialFolder+"aug_numFakesDetected1.pickle", 'wb') as handle:
    #     pickle.dump(numFakesDetected, handle, protocol=pickle.HIGHEST_PROTOCOL)
    # #plot line graph of FPrates vs sensitivities
    # #idk if this will actually work, it's modified from a stack overflow post
    #
    # plt.gcf().clear()
    # plt.plot(FPrates, sensitivities)
    # plt.xlabel('FPs per Scan', fontsize = 16)
    # plt.ylabel("% Nodules Detected", fontsize = 16)
    # plt.title("FROC Curve, Certain Nodules", fontsize = 24)
    # plt.ylim([0,1])
    # plt.tick_params(labelsize = 12)
    # plt.savefig(trialFolder+'aug_FROC_plot1.png')
    #
    #
    # plt.gcf().clear()
    # plt.plot(FPratesAdj, sensitivities)
    # plt.xlabel('FPs per Scan, Adjusted', fontsize = 16)
    # plt.ylabel("% Nodules Detected", fontsize = 16)
    # plt.title("FROC Curve, Certain Nodules", fontsize = 24)
    # plt.ylim([0,1])
    # plt.tick_params(labelsize = 12)
    # plt.savefig(trialFolder+'aug_FROC_plotAdj1.png')
    #
    #
    # plt.gcf().clear()
    # plt.plot(FPrates, fakeSensitivities)
    # plt.xlabel('FPs per Scan', fontsize = 16)
    # plt.ylabel("% Nodules Detected", fontsize = 16)
    # plt.title("FROC Curve, All Nodules", fontsize = 24)
    # plt.ylim([0,1])
    # plt.tick_params(labelsize = 12)
    # plt.savefig(trialFolder+'aug_FROC_plot21.png')

