import csv
import os
from mantid.simpleapi import *
import numpy as np
from mantid.geometry import CrystalStructure, ReflectionGenerator, ReflectionConditionFilter
import matplotlib.pyplot as plt
from mantid.plots.utility import MantidAxType
from mantid.api import AnalysisDataService as ADS
from mantid.kernel import Atom

from mantid.geometry import PointGroupFactory
from mantid.geometry import SpaceGroupFactory
#this is a test by Jasmine K. Hinton# 

defaultCifFolder = '/SNS/SNAP/shared/cifLibrary'

class Box():


    '''class to hold list of peaks and their properties'''

    def __init__(self,cif):
 
        self.defaultCifFolder = defaultCifFolder
        self.cifSpec = cif
        self.nickName = ''

        #locate and validate cif path using cifSpec.
        self.validCif = self.findCif()
        if not self.validCif:
            print('ERROR: validCif failed')

        self.dMin = 0.5
        self.dMax = 100
 
        self.modifiedLattice = False # if false allows scaling of lattice
        if self.validCif:
            self.loadCif()           

        self.tickWSExists = False

        #plotting attributes
        self.markerHeight = 10
        self.markeredgecolor='red'


    def findCif(self):


        dirname = os.path.dirname(self.cifSpec)

        if self.cifSpec[-3:].lower() != 'cif':
            # look for a standard material: one that's listed by nickname in file cifIndex.csv 
            # stored in defaultCifFolder
            nickName=[]
            cifFilename=[]
            with open(f"{self.defaultCifFolder}/nickNames.csv", mode = 'r') as file:
                csvFile = csv.reader(file)
                for line in csvFile:
                    nickName.append(line[0].lower()) #enforce lower case
                    cifFilename.append(line[1])
            try:
                foundIndex = nickName.index(self.cifSpec.lower())
                self.cifFilePath=f"{self.defaultCifFolder}/{cifFilename[foundIndex]}"
                self.nickName=self.cifSpec.lower()
                
            except:
                print(f"ERROR: cif specification {self.cifSpec} diamond failed")
                return False
            
            if os.path.isfile(self.cifFilePath):
                return True
            else:
                print(f"ERROR: tried and failed to open: {self.cifFilePath}")
                return False
            
        if (self.cifSpec[-3:].lower() == 'cif') and (dirname==''):

            #first see if file is in current working directory
            cwd =  os.path.dirname(__file__)
            cwdPath = f"{cwd}/{self.cifSpec}"
            if os.path.isfile(cwdPath):
                self.cifFilePath=cwdPath
                return True
            #next check defaultCifFolder
            
            libPath = f"{self.defaultCifFolder}/{self.cifSpec}"
            if os.path.isfile(libPath):
                self.cifFilePath = libPath
                return True
        
            print("ERROR: couldn\'t read cif file after checking these locations")
            print(cwdPath)
            print(libPath)
            return False

        if (self.cifSpec[-3:].lower() == 'cif') and (dirname != ''):

            if os.path.isfile(self.cifSpec):
                self.cifFilePath = self.cifSpec
                return True
            else:
                print("ERROR couldn\'t read this file: {self.cifSpec}")        
            
    def loadCif(self):
        CreateSampleWorkspace(OutputWorkspace='tmp')
        LoadCIF(Workspace='tmp',InputFile=self.cifFilePath)
        ws = mtd['tmp']
        self._originalCrystal  = ws.sample().getCrystalStructure()
        self._originalUnitCell = ws.sample().getCrystalStructure().getUnitCell()
                

        #get scatterers
        self.cellContents = self._originalCrystal.getScatterers()
        self._originalCellContents = self.parseCellContents()
        self.processCrystal(self._originalCrystal)
        # current values for lattice params are fresh from cif and unmodified. Keep a copy of these
        self.a_orig = self.a
        self.b_orig = self.b
        self.c_orig = self.c
        self.alpha_orig = self.alpha
        self.beta_orig = self.beta
        self.gamma_orig = self.gamma

        DeleteWorkspace(Workspace='tmp')
    
    
    def processCrystal(self,crystal):
   
        unitCell = crystal.getUnitCell()

        # some symmetry parameters
        self.HMSymbol = crystal.getSpaceGroup().getHMSymbol()
        self.pointGroup = crystal.getSpaceGroup().getPointGroup()
        
        #define useful crystallographic attributes
        self.a = unitCell.a()
        self.b = unitCell.b()
        self.c = unitCell.c()
        self.alpha = unitCell.alpha() 
        self.beta = unitCell.beta() 
        self.gamma = unitCell.gamma()
        self.volume = unitCell.volume()
        self.astar = unitCell.astar()
        self.bstar = unitCell.bstar()
        self.cstar = unitCell.cstar()
        self.alphastar = unitCell.alphastar()
        self.betastar = unitCell.betastar()
        self.gammastar = unitCell.gammastar()

        #JKH added to make use in cartesian hkl method
        self.BMatrix = unitCell.getB()
        
        #Generate reflections
        generator = ReflectionGenerator(crystal)
        # Create list of unique reflections between 0.7 and 3.0 Angstrom
        hkls = generator.getUniqueHKLsUsingFilter(self.dMin, self.dMax, ReflectionConditionFilter.StructureFactor)
        # Calculate d and F^2
        dValues = generator.getDValues(hkls)
        fSquared = generator.getFsSquared(hkls)
        
        # Make list of tuples and sort by d-values, descending, include point group for multiplicity.
        reflections = sorted([(hkl, d, fsq, len(self.pointGroup.getEquivalents(hkl))) for hkl, d, fsq in zip(hkls, dValues, fSquared)],
                                    key=lambda x: x[1] - x[0][0]*1e-6, reverse=True)

        # create individual lists of reflection properties with shared order and useful names

        self.nRef = len(reflections)
        self.hkl = []
        self.dSpacing = []
        self.fSq = []
        self.mult = []
        self.estInt = []
        for i in range(self.nRef):
            self.hkl.append(reflections[i][0])
            self.dSpacing.append(reflections[i][1])
            self.fSq.append(reflections[i][2])
            self.mult.append(reflections[i][3])
            Amp = reflections[i][2]*reflections[i][3]*reflections[i][1]**4 #Fsq times multiplicity * d**4
            self.estInt.append(Amp)
        

    def summary(self):
        print(f"\nCIF file: {self.cifFilePath}")
        print(f"phase nickname: {self.nickName}")
        print(f"Space Group: {self.HMSymbol}")
        print(f"a: {self.a:.4f} Ang, b: {self.b:.4f} Ang, c: {self.c:.4f} Ang")
        print(f"alp: {self.alpha:.1f} deg, beta: {self.beta:.1f} deg, gam: {self.gamma:.1f} deg")
        print(f"{self.nRef} reflections calculated")
        print(f"First 10 reflections:")
        for ref in range(self.nRef):
            print(f"{self.hkl[ref]} {self.dSpacing[ref]:4f} {self.mult[ref]} {self.fSq[ref]:.4f}")

    def tickWS(self,yVal):

        self.tickWSExists = True
        self.tickWSName = f"ticks: {self.nickName}"
        self.tickWSyVal = yVal

        dataXArray = np.array(self.dSpacing)
        dataYArray = np.ones_like(dataXArray)*self.tickWSyVal
        CreateWorkspace(OutputWorkspace=self.tickWSName,
                        DataX = dataXArray,
                        DataY = dataYArray,
                        UnitX = 'd-Spacing')
        
    def scaleLattice(self,scaleFactor):
        #includes code from Z. Morgan https://github.com/zjmorgan/NeuXtalViz/blob/main/src/NeuXtalViz/models/crystal_structure_tools.py

        self.modifiedLattice = True
        self.latticeScaleFactor = scaleFactor
        # have to build a new CrystalStructure
        # first need ingredients for this:
        params = [self.a_orig*scaleFactor,
                  self.b_orig*scaleFactor,
                  self.c_orig*scaleFactor,
                  self.alpha_orig,
                  self.beta_orig,
                  self.gamma_orig]
        
        print(params)
        
        scatterers = self.parseCellContents()

        line = ' '.join(['{}']*6)
        constants = line.format(*params)

        atom_info = ';'.join([line.format(*s) for s in scatterers])

        #then build CrystalStructure
        crystal_mod = CrystalStructure(constants,self.HMSymbol, atom_info)

        #now process this to update current crystal attributes
        self.processCrystal(crystal_mod)

        #if workspace exists, need to update it with scaled d-spacings
        if self.tickWSExists:
            self.tickWS(self.tickWSyVal)

        return
    
    def parseCellContents(self):
        #includes code from Z. Morgan https://github.com/zjmorgan/NeuXtalViz/blob/main/src/NeuXtalViz/models/crystal_structure_tools.py
        print('Parsing contents of unit-cell')
        scatterers = self.cellContents
        scatterers = [atm.split(' ') for atm in list(scatterers)]
        scatterers = [[val if val.isalpha() else float(val) \
                       for val in scatterer] for scatterer in scatterers]
        return scatterers
          

    def fixUiso(self):
        contents=self.parseCellContents()
        for i in range(0,len(contents)):
            Mass = Atom(contents[i][0]).mass
            #A factor of 10 is added here to make the F2 numbers less vanishingly small
            contents[i][5] = 1/(30*np.sqrt(Mass))

        modifiedContents = "; ".join([f'{scatterer[0]} {scatterer[1]} {scatterer[2]} {scatterer[3]} {scatterer[4]} {scatterer[5]}' for scatterer in contents])

        #Rebuild the crystal structure
        latticeParams = f"{self.a} {self.b} {self.c} {self.alpha} {self.beta} {self.gamma}"
        crystalMod = CrystalStructure(latticeParams, self.HMSymbol, modifiedContents)
        #Update current crystal 
        self.cellContents = crystalMod.getScatterers()
        self.processCrystal(crystalMod)
    
    def resetCell(self):
        #Resets the crystal contents to those loaded from teh cif, lattice params, cell contents, and Uiso
        #Call original cell and reformat back into correct form
        oldCellContents = self._originalCellContents
        modifiedContents = "; ".join([f'{scatterer[0]} {scatterer[1]} {scatterer[2]} {scatterer[3]} {scatterer[4]} {scatterer[5]}' for scatterer in oldCellContents])
        #Rebuild the crystal structure and reset lattive parameters
        latticeParams = f"{self._originalUnitCell.a()} {self._originalUnitCell.b()} {self._originalUnitCell.c()} {self._originalUnitCell.alpha()} {self._originalUnitCell.beta()} {self._originalUnitCell.gamma()}"
        crystalMod = CrystalStructure(latticeParams, self.HMSymbol, modifiedContents)
        #Update current crystal 
        self.cellContents = crystalMod.getScatterers()
        self.processCrystal(crystalMod)

    def resetLattice(self):

        self.modifiedLattice = False
        self.scaleLattice(1.0)

        return
    
    def plot(self,workspaceToPlot):
                        
        """workspaceToPlot is the an existing workspace that will be plotted along wit the ticks 
        """

        ticks = ADS.retrieve(self.tickWSName)
        if workspaceToPlot != '':
            dataToPlot = ADS.retrieve(workspaceToPlot)
            nHst = mtd[workspaceToPlot].getNumberHistograms()
            if nHst >= 7:
                nHst=6
                print("WARNING: can only plot first 6 spectra!")


        fig, axes = plt.subplots(edgecolor='#ffffff', num='ticks plot', subplot_kw={'projection': 'mantid'})
        lineColours = ['#1f77b4','#ff7f0e','#2ca02c','#d62728','#9467bd','#8c564b']

        axes.plot(ticks, color='#1f77b4', 
                  label=f"ticks: {self.nickName}", 
                  linestyle='None', 
                  marker='|', 
                  markersize=self.markerHeight,
                  markeredgecolor=self.markeredgecolor, 
                  wkspIndex=0)

        if workspaceToPlot != '':
            for spectrum in range(nHst):
                axes.plot(dataToPlot,wkspIndex=spectrum,color=lineColours[spectrum],label=f"spec{spectrum}")

        axes.tick_params(axis='x', which='major', **{'gridOn': False, 'tick1On': True, 'tick2On': False, 'label1On': True, 'label2On': False, 'size': 6, 'tickdir': 'out', 'width': 1})
        axes.tick_params(axis='y', which='major', **{'gridOn': False, 'tick1On': True, 'tick2On': False, 'label1On': True, 'label2On': False, 'size': 6, 'tickdir': 'out', 'width': 1})
        axes.set_title(f"ticks: {self.nickName}")
        axes.set_xlabel('d-Spacing ($d-Spacing$)')
        axes.set_ylabel('($d-Spacing$)$^{-1}$')
        # axes.set_xlim([0.4448, 2.0285])
        # axes.set_ylim([0.14175, 0.15825])
        legend = axes.legend(fontsize=8.0).set_draggable(True).legend

        plt.show()

    def dLimits(self,dMin,dMax):
        self.dMin=dMin
        self.dMax=dMax
        self.loadCif()

    #########################################################################
    #                           jasmineFunction                             #
    #   jasmineFunction is the first function I made in here because I was  #
    #   afraid of messing up Malcolm's code and was learning how commmits   #
    #   and pull requests work. Now it's a monument and marker to my edits  #                     
    #########################################################################

    def jasmineFunction(self):
        print("This is Jasmine's Function")
    
    #########################################################################
    #                           defineSpaceGroup                            #
    #   defineSpaceGroup is intended to pull the space group from the cif,  #
    #   and create a point group from it. I found I was using it a lot in   #
    #   other methods so I may add this method into those? Later note: I    #
    #   tried this and I can't call a method I wrote in crystal box in here #
    #########################################################################
    
    def defineSpaceGroup(self):
        sg = SpaceGroupFactory.createSpaceGroup(self.HMSymbol)
        pg = PointGroupFactory.createPointGroupFromSpaceGroup(sg)
        return pg
    
    #########################################################################
    #                           getEquivalents                              #
    #   getEquivalents is intended to take a reflection, pull the space     #
    #   group from the cif, create a point group, and then provide all the  #
    #   equivalent reflections of that given hkl.                           #
    #########################################################################

    def getEquivalents(self, hkl):
        sg = SpaceGroupFactory.createSpaceGroup(self.HMSymbol)
        pg = PointGroupFactory.createPointGroupFromSpaceGroup(sg)

        equivalents = pg.getEquivalents(hkl)
        
        print(sg)
        print(pg)
        print("The equivalents of reflection", hkl, "include the following:", equivalents)
        print ("Number of reflections equivalent to ", hkl, "is", len(equivalents[0]))
       
    #########################################################################
    #                           cartesianHKL                                #
    #   the purpose of cartesianHKL is to take a vector, in this case,      #
    #   likely a set of 3 q-coordinates, and if they're not cartesian, then #
    #   multiply by the b-matrix (obtained in process crystal method) and   #
    #   the resulting vector should then be cartesian. It now actually      #
    #   verifies the crystal system has a cartesian basis and proceeds with #
    #   the calculation if so. Otherwise it says you you can skip this step #                                                                   #
    #########################################################################
    
    def cartesianHKL(self,h):

        sg = SpaceGroupFactory.createSpaceGroup(self.HMSymbol)
        pg = PointGroupFactory.createPointGroupFromSpaceGroup(sg)
        crystalSystem = str(pg.getCrystalSystem())

        if crystalSystem == "Cubic" or crystalSystem == "Orthorhombic" or crystalSystem == "Tetragonal":
            print("Crystal system is ", crystalSystem)
            print("Crystal system has cartesian basis and does not need to be converted via cartesianHKL.",
                  "You may proceed to calculating angle if you wish.")
        else:
            print("Crystal system is ", crystalSystem)
            print("pg.getCrystalSystem() outputs a variable of type:", type(crystalSystem))
            print("Crystal system does not have cartesian basis and will now be converted via caresianHKL")
            
            v = np.matmul(self.BMatrix,h)
            return v
    
    #########################################################################
    #                           getAngle                                    #
    #   getAngle is intended to take two vectors and calculate the angle    #
    #   between them in degrees. A boolean variable called degrees is       #
    #   assigned to help the user know that the result will be in degrees   #
    #   and not radians. It is assumed that the vectors are on an           #
    #   an orthonormal cartesian basis. If they are not, it is recommended  #
    #   to use the method cartesian hkl first.                              #
    #########################################################################

    def getAngle(self,vector1,vector2, degrees=True):
        
        print("Ensure your vectors are in a cartesian basis set before using this method,",
              "otherwise your result will not be meaningful.",
              "Use method, 'cartesianHKL' to verify this.")
        
        angle_rad_q_obs = np.arccos(np.dot(vector1,vector2)/(np.linalg.norm(vector1)*
            np.linalg.norm(vector2)))
        angle_deg_q_obs = np.degrees(angle_rad_q_obs)
        
        print ("Input vectors were", vector1,"and", vector2,
               ". The angle between these two vectors is", angle_deg_q_obs, "degrees.")
        print("Angle is in degrees =", degrees)
        #self.loadCif()
        self.loadCifNormUiso()

    def getEquivalents(self, hkl):
        sg = SpaceGroupFactory.createSpaceGroup(self.HMSymbol)
        pg = PointGroupFactory.createPointGroupFromSpaceGroup(sg)
        
        equivalents = pg.getEquivalents(hkl)
        
        print(sg)
        print(pg)
        print("The equivalents of reflection", hkl, "include the following:", equivalents)    

        return #angle_deg_q_obs                
    
    #########################################################################
    #                           makeCrystal                                 #
    #   this is where I would put my description of this method             #
    #   ...if I had one!!                                                   #
    #(https://imgflip.com/s/meme/This-Is-Where-Id-Put-My-Trophy-If-I-Had-One.jpg)#
    #   (this is a work in progress in other words),                        #
    #########################################################################
    
    def makeCrystal(self):
        params = [self.a_orig,
                  self.b_orig,
                  self.c_orig,
                  self.alpha_orig,
                  self.beta_orig,
                  self.gamma_orig]
        #print(params)
        line = ' '.join(['{}']*6)
        constants = line.format(*params)
        scatterers = self.get_scatterers()
        atom_info = ';'.join([line.format(*s) for s in scatterers])
        crystal_structure = CrystalStructure(constants,self.HMSymbol, atom_info)
        
        return crystal_structure 
        
def showNicknames():
    print('available nicknames are:')
    with open(f"{defaultCifFolder}/nickNames.csv", mode = 'r') as file:
        csvFile = csv.reader(file)
        for line in csvFile:
            print(line[0].lower())
