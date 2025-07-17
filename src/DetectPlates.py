import cv2
import numpy as np
import math
import random

import Preprocess
import DetectChars
import PossiblePlate

# Constants
PLATE_WIDTH_PADDING_FACTOR = 1.3
PLATE_HEIGHT_PADDING_FACTOR = 1.5

class PossiblePlate:
    """Class to represent a possible license plate"""
    
    def __init__(self):
        self.imgPlate = None
        self.imgGrayscale = None
        self.imgThresh = None
        
        self.rrLocationOfPlateInScene = None
        
        self.strChars = ""

def detectPlatesInScene(imgOriginalScene):
    """Detect possible license plates in scene"""
    listOfPossiblePlates = []
    
    height, width, numChannels = imgOriginalScene.shape
    
    imgGrayscaleScene = np.zeros((height, width, 1), np.uint8)
    imgThreshScene = np.zeros((height, width, 1), np.uint8)
    imgContours = np.zeros((height, width, 3), np.uint8)
    
    cv2.destroyAllWindows()
    
    imgGrayscaleScene, imgThreshScene = Preprocess.preprocess(imgOriginalScene)
    
    listOfPossibleCharsInScene = findPossibleCharsInScene(imgThreshScene)
    
    listOfListsOfMatchingCharsInScene = DetectChars.findListOfListsOfMatchingChars(listOfPossibleCharsInScene)
    
    for listOfMatchingChars in listOfListsOfMatchingCharsInScene:
        possiblePlate = extractPlate(imgOriginalScene, listOfMatchingChars)
        
        if possiblePlate.imgPlate is not None:
            listOfPossiblePlates.append(possiblePlate)
    
    return listOfPossiblePlates

def findPossibleCharsInScene(imgThresh):
    """Find possible characters in scene"""
    listOfPossibleChars = []
    
    intCountOfPossibleChars = 0
    
    imgThreshCopy = imgThresh.copy()
    
    contours, npaHierarchy = cv2.findContours(imgThreshCopy, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    
    height, width = imgThresh.shape
    imgContours = np.zeros((height, width, 3), np.uint8)
    
    for i in range(0, len(contours)):
        cv2.drawContours(imgContours, contours, i, (255, 255, 255))
    
    for contour in contours:
        possibleChar = DetectChars.ContourWithData()
        possibleChar.npaContour = contour
        possibleChar.boundingRect = cv2.boundingRect(contour)
        possibleChar.calculateRectTopLeftPointAndWidthAndHeight()
        possibleChar.fltArea = cv2.contourArea(contour)
        
        if checkIfContourIsValidChar(possibleChar):
            intCountOfPossibleChars += 1
            listOfPossibleChars.append(possibleChar)
    
    return listOfPossibleChars

def checkIfContourIsValidChar(possibleChar):
    """Check if contour is a valid character"""
    if (possibleChar.fltArea > DetectChars.MIN_CONTOUR_AREA and
        possibleChar.intRectWidth > DetectChars.MIN_PIXEL_WIDTH and
        possibleChar.intRectHeight > DetectChars.MIN_PIXEL_HEIGHT and
        DetectChars.MIN_ASPECT_RATIO < (possibleChar.intRectWidth / possibleChar.intRectHeight) < DetectChars.MAX_ASPECT_RATIO):
        return True
    else:
        return False

def extractPlate(imgOriginal, listOfMatchingChars):
    """Extract plate from original image"""
    possiblePlate = PossiblePlate()
    
    listOfMatchingChars.sort(key=lambda matchingChar: matchingChar.intRectX)
    
    fltPlateCenterX = (listOfMatchingChars[0].intRectX + listOfMatchingChars[len(listOfMatchingChars) - 1].intRectX + listOfMatchingChars[len(listOfMatchingChars) - 1].intRectWidth) / 2.0
    fltPlateCenterY = (listOfMatchingChars[0].intRectY + listOfMatchingChars[0].intRectHeight) / 2.0
    
    ptPlateCenter = fltPlateCenterX, fltPlateCenterY
    
    intPlateWidth = int((listOfMatchingChars[len(listOfMatchingChars) - 1].intRectX + listOfMatchingChars[len(listOfMatchingChars) - 1].intRectWidth - listOfMatchingChars[0].intRectX) * PLATE_WIDTH_PADDING_FACTOR)
    
    intTotalOfCharHeights = 0
    
    for matchingChar in listOfMatchingChars:
        intTotalOfCharHeights += matchingChar.intRectHeight
    
    fltAverageCharHeight = intTotalOfCharHeights / len(listOfMatchingChars)
    
    intPlateHeight = int(fltAverageCharHeight * PLATE_HEIGHT_PADDING_FACTOR)
    
    fltOppositeOfAngle = listOfMatchingChars[len(listOfMatchingChars) - 1].intRectY - listOfMatchingChars[0].intRectY
    fltHypotenuseOfAngle = DetectChars.distanceBetweenChars(listOfMatchingChars[0], listOfMatchingChars[len(listOfMatchingChars) - 1])
    fltCorrectionAngleInRad = math.atan(fltOppositeOfAngle / fltHypotenuseOfAngle)
    fltCorrectionAngleInDeg = fltCorrectionAngleInRad * (180.0 / math.pi)
    
    possiblePlate.rrLocationOfPlateInScene = (tuple(ptPlateCenter), (intPlateWidth, intPlateHeight), fltCorrectionAngleInDeg)
    
    rotationMatrix = cv2.getRotationMatrix2D(tuple(ptPlateCenter), fltCorrectionAngleInDeg, 1.0)
    
    height, width, numChannels = imgOriginal.shape
    
    imgRotated = cv2.warpAffine(imgOriginal, rotationMatrix, (width, height))
    
    imgCropped = cv2.getRectSubPix(imgRotated, (intPlateWidth, intPlateHeight), tuple(ptPlateCenter))
    
    possiblePlate.imgPlate = imgCropped
    
    return possiblePlate
