"""
<name>GSEA</name>
<description>Gene Set Enrichment Analysis</description>
<contact>Marko Toplak (marko.toplak(@at@)gmail.com)</contact>
<priority>210</priority>
<icon>icons/GSEA.png</icon>
"""

from OWWidget import *
import OWGUI
import orngGsea
from exceptions import Exception

def nth(l, n):
    return [ a[n] for a in l ]

def clearListView(lw):
    it = lw.firstChild()
    while it:
        lw.takeItem(it)
        it = lw.firstChild()

def dataWithAttrs(data, attributes):
    attributes = dict([(a,1) for a in attributes])
    newatts = [ a for a in data.domain.attributes if a.name in attributes ]
    if data.domain.classVar:
        domain = orange.Domain(newatts, data.domain.classVar)
    else:
        domain = orange.Domain(newatts, False)
    return orange.ExampleTable(domain, data)

def comboboxItems(combobox, newitems):
    combobox.clear()
    if newitems:
        combobox.insertStrList(newitems)
        #combobox.setCurrentItem(i)

def getClasses(data):
    return [ str(a) for a in data.domain.classVar ]

class PhenotypesSelection():

    def __init__(self, parent, s1=0, s2=1):
        grid = QHBox(parent)
        grid.setMinimumWidth(250)
        grid.setMinimumHeight(100)

        self.p1b = QListBox(grid)
        self.p2b = QListBox(grid)

        QObject.connect(self.p1b,  SIGNAL("highlighted ( int )"), self.highlighted1)
        QObject.connect(self.p2b,  SIGNAL("highlighted ( int )"), self.highlighted2)

        self.classes = []

        def createSquarePixmap(color = Qt.black):
            pixmap = QPixmap()
            pixmap.resize(13, 13)
            painter = QPainter()
            painter.begin(pixmap)
            painter.setPen(color);
            painter.setBrush(color);
            painter.drawRect(0, 0, 13, 13);
            painter.end()
            return pixmap

        self.whiteSq = createSquarePixmap(Qt.white)
        self.redSq = createSquarePixmap(Qt.red)
        self.blueSq = createSquarePixmap(Qt.blue)

        self.classVals = []

        self.setStates(s1, s2)

    def setStates(self, s1 = 0, s2 = 1):

        self.state1 = self.ls1 = s1
        self.state2 = self.ls2 = s2

        if self.state1 == self.state2:
            if self.state1 == 0: self.state2 = 1
            else: self.state2 = 0

        self.selectWanted()

    def selectWanted(self):

        self.disableNot = True

        try:
            self.p1b.changeItem(self.whiteSq, self.classVals[self.ls1], self.ls1)
            self.p2b.changeItem(self.whiteSq, self.classVals[self.ls2], self.ls2)
        except:
            #except can happen only if both are illegal
            pass

        try:
            self.p1b.setCurrentItem(self.state1)
            self.p2b.setCurrentItem(self.state2)
            self.p1b.changeItem(self.redSq, self.classVals[self.state1], self.state1)
            self.p2b.changeItem(self.blueSq, self.classVals[self.state2], self.state2)
            self.ls1 = self.state1
            self.ls2 = self.state2
        except:
            pass

        self.disableNot = False

    def highlighted1(self, i):
        if self.disableNot:
            return
        if i == self.state2:
            self.state2 = self.state1
        self.state1 = i
        self.selectWanted()

    def highlighted2(self, i):
        if self.disableNot:
            return
        if i == self.state1:
            self.state1 = self.state2
        self.state2 = i
        self.selectWanted()

    def setClasses(self, input, s1=0, s2=1):
        self.classVals = sorted(input)
        self.setupBoxes()
        self.selectWanted()
        self.setStates(s1,s2)

    def getSelection(self):
        return (self.classVals[self.state1], self.classVals[self.state2])

    def setupBoxes(self):
        self.setupBox(self.p1b)
        self.setupBox(self.p2b)

    def setupBox(self, box):
        box.clear()
        for cv in self.classVals:
            box.insertItem(self.whiteSq, cv)
        if not self.classVals:
            box.setDisabled(True)
        else:
            box.setDisabled(False)



class OWGsea(OWWidget):

    settingsList = [ "name", "perms", "minSubsetSize", "minSubsetSizeC", "maxSubsetSize", "maxSubsetSizeC", \
        "minSubsetPart", "minSubsetPartC", "ptype" ]

    def __init__(self, parent=None, signalManager = None, name='GSEA'):
        OWWidget.__init__(self, parent, signalManager, name)

        self.inputs = [("Examples", ExampleTable, self.setData)]
        self.outputs = [("Examples with selected genes only", ExampleTable), ("Results", ExampleTable) ]

        self.res = None

        self.name = 'GSEA'
        self.minSubsetSize = 3
        self.minSubsetSizeC = True
        self.maxSubsetSize = 1000
        self.maxSubsetSizeC = True
        self.minSubsetPart = 10
        self.minSubsetPartC = True
        self.perms = 100

        self.permutationTypes =  [("Phenotype", "p"),("Gene", "g") ]
        self.ptype = 0

        self.correlationTypes = [ ("Signal2Noise", "s2n") ]
        self.ctype = 0

        #self.loadSettings()
        self.data = None
        self.geneSets = {}

        ca = self.controlArea
        ca.setMaximumWidth(500)

        box = QVGroupBox(ca)
        box.setTitle('Permutate')

        self.permTypeF = OWGUI.comboBox(box, self, "ptype", items=nth(self.permutationTypes, 0), \
            tooltip="Permutation type.")

        _ = OWGUI.spin(box, self, "perms", 50, 1000, orientation="horizontal", label="Times")

        OWGUI.separator(ca)

        box = QVGroupBox(ca)
        box.setTitle('Correlation Calculation')

        self.corTypeF = OWGUI.comboBox(box, self, "ctype", items=nth(self.correlationTypes, 0), \
            tooltip="Correlation type.")

        OWGUI.separator(ca)

        box = QVGroupBox(ca)
        box.setTitle('Subset Filtering')

        _,_ = OWGUI.checkWithSpin(box, self, "Min. Subset Size", 1, 10000, "minSubsetSizeC", "minSubsetSize", "") #TODO check sizes
        _,_ = OWGUI.checkWithSpin(box, self, "Max. Subset Size", 1, 10000, "maxSubsetSizeC", "maxSubsetSize", "")
        _,_ = OWGUI.checkWithSpin(box, self, "Min. Subset Part (%)", 1, 100, "minSubsetPartC", "minSubsetPart", "")

        ma = self.mainArea
        boxL = QVBoxLayout(ma, QVBoxLayout.TopToBottom)
        #box.setTitle("Results")

        self.listView = QListView(ma)
        for header in ["Geneset", "NES", "ES", "P-value", "Size", "Matched Size", "Genes"]:
            self.listView.addColumn(header)
        self.listView.setSelectionMode(QListView.NoSelection)
        self.connect(self.listView, SIGNAL("selectionChanged ( QListViewItem * )"), self.newPathwaySelected)
        boxL.addWidget(self.listView)

        OWGUI.separator(ca)

        box = QVGroupBox(ca)
        box.setTitle("Phenotypes")

        self.psel = PhenotypesSelection(box)

        self.resize(600,50)
 
        OWGUI.separator(ca)
        self.btnApply = OWGUI.button(ca, self, "&Compute", callback = self.compute, disabled=0)

        gen1 = getGenesets()

        for name,genes in gen1.items():
            self.addGeneset(name, genes)

        self.addComment("Computation was not started.")

    def newPathwaySelected(self, item):

        qApp.processEvents()

        if not self.selectable:
            return

        iname = self.lwiToGeneset[item]
        outat = self.res[iname][6]

        dataOut =  dataWithAttrs(self.data, outat)
        self.send("Examples with selected genes only", dataOut)

    def resultsOut(self, data):
        self.send("Results", data)

    def exportET(self, res):
        
        if len(res) <= 0:
            return None

        vars = []
        vars.append(orange.StringVariable("Name"))
        vars.append(orange.FloatVariable("NES"))
        vars.append(orange.FloatVariable("ES"))
        vars.append(orange.FloatVariable("P-value"))
        vars.append(orange.FloatVariable("FDR"))
        vars.append(orange.StringVariable("Geneset size"))
        vars.append(orange.StringVariable("Matched size"))
        vars.append(orange.StringVariable("Genes"))
    
        domain = orange.Domain(vars, False)

        examples = []
        for name, (es, nes, pval, fdr, os, ts, genes) in res.items():
            examples.append([name, nes, es, pval, fdr, str(os), str(ts),  ", ".join(genes)])

        return orange.ExampleTable(domain, examples)

    def fillResults(self, res):

        clearListView(self.listView)

        self.lwiToGeneset = {}

        def writeGenes(g):
            return ", ".join(genes)

        for name, (es, nes, pval, fdr, os, ts, genes) in res.items():
            item = QListViewItem(self.listView)
            item.setText(0, name)
            item.setText(1, "%0.3f" % nes)
            item.setText(2, "%0.3f" % es)
            item.setText(3, "%0.3f" % pval)
            #item.setText(4, "%0.3f" % min(fdr,1.0))
            item.setText(4, str(os))
            item.setText(5, str(ts))
            item.setText(6, writeGenes(genes))

            self.lwiToGeneset[item] = name

    def addComment(self, comm):
        item = QListViewItem(self.listView)
        item.setText(0, comm)

    def setSelMode(self, bool):
        if bool:
            self.selectable = True
            self.listView.setSelectionMode(QListView.Single)
        else:
            self.selectable = False
            self.listView.setSelectionMode(QListView.NoSelection)

    def compute(self):

        clearListView(self.listView)
        self.addComment("Computing...")

        self.resultsOut(None)

        qApp.processEvents()

        if self.data:

            self.setSelMode(False)

            pb = OWGUI.ProgressBar(self, iterations=self.perms+2)

            if hasattr(self, "btnApply"):
                self.btnApply.setFocus()

            kwargs = {}

            def ifr(case, t, f):
                if case: return t
                else: return f

            kwargs["minSize"] = \
                ifr(self.minSubsetSizeC, self.minSubsetSize, 1)
            kwargs["maxSize"] = \
                ifr(self.maxSubsetSizeC, self.maxSubsetSize, 1000000)
            kwargs["minPart"] = \
                ifr(self.minSubsetPartC, self.minSubsetPart/100.0, 0.0)
 
            dkwargs = {}
            if len(self.data) > 1:
                dkwargs["classValues"] = self.psel.getSelection()
 
            gso = orngGsea.GSEA(organism="hsa")
            gso.setData(self.data, **dkwargs)

            for name,genes in self.geneSets.items():
                gso.addGeneset(name, genes)
                qApp.processEvents()

            self.res = gso.compute(n=self.perms, callback=pb.advance, **kwargs)
            
            pb.finish()

            if len(self.res) > 0:
                self.fillResults(self.res)
                self.setSelMode(True)
                self.resultsOut(self.exportET(self.res))
            else:
                self.setSelMode(False)
                clearListView(self.listView)
                self.addComment("No genesets found.")


    def setData(self, data):
        self.data = data

        if data:
            if len(data) == 1:
                #disable correlation type
                comboboxItems(self.corTypeF, [])
                self.corTypeF.setDisabled(True)
                #set permutation type to fixed
                self.permTypeF.setCurrentItem(1)
                self.permTypeF.setDisabled(True)
                
                self.psel.setClasses([])
            else:
                #enable correlation type
                comboboxItems(self.corTypeF, nth(self.correlationTypes, 0))
                self.corTypeF.setDisabled(False)
                #allow change of permutation type
                self.permTypeF.setDisabled(False)

                self.psel.setClasses(getClasses(data))

    def addGeneset(self, name, genes):
        self.geneSets[name] = genes


def unpckGS(filename):
    import pickle
    f = open(filename,'rb')
    return pickle.load(f)

def getGenesets():
    import orngRegistry
    return unpckGS(orngRegistry.bufferDir + "/gsea/geneSets_Gsea_KEGGhsa.pck")

if __name__=="__main__":
    a=QApplication(sys.argv)
    ow=OWGsea()
    a.setMainWidget(ow)
    ow.show()

    #d = orange.ExampleTable('DLBCL_200a.tab')
    #d = orange.ExampleTable('brown-selected.tab')

    #d = orange.ExampleTable('testCorrelated.tab')
    #ow.setData(d)

    #d = orange.ExampleTable("sterolTalkHepa.tab")
    #ow.setData(d)

    d = orange.ExampleTable("demo.tab")
    ow.setData(d)

    #d = orange.ExampleTable("tmp.tab")
    #ow.setData(d)



    a.exec_loop()
    ow.saveSettings()