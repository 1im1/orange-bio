"""
<name>KEGG Pathway Browser</name>
<description>Browse KEGG pathways that include an input set of genes.</description>
<priority>2030</priority>
<icon>icons/KEGG.png</icon>
"""
from __future__ import with_statement 

import sys
import orange
import obiKEGG, orngServerFiles
import obiTaxonomy

from OWWidget import *
import OWGUI
from collections import defaultdict

def split_and_strip(string, sep=None):
    return [s.strip() for s in string.split(sep)]

class PathwayToolTip(object):
    def __init__(self, parent):
        self.parent = parent

    def maybeTip(self, p):
        objs = [(id, bb) for id, bb in self.parent.GetObjects(p.x() ,p.y()) if id in self.parent.objects]
        if objs:
            genes = map(self.parent.master.uniqueGenesDict.get, dict(objs).keys())
            name = objs[0][1].get("name", "")
            text = "<br>".join(genes)
            if name:
                text = "<p>" + name + "</p>" + text
##            self.tip(QRect(p.x()-2, p.y()-2, 4, 4), text)
            QToolTip.showText(self.parent.mapToGlobal(p), text, self.parent, QRect(p.x()-2, p.y()-2, 4, 4))

class PathwayView(QGraphicsView):
    def __init__(self, master, *args):
        QGraphicsView.__init__(self, *args)
        self.master = master
        self.toolTip = PathwayToolTip(self)

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self.graphics_items = []
        self.pixmap = None
        self.image = None       
        
        self.popup = QMenu(self)
        self.popup.addAction("View genes on KEGG website", self.PopupAction)
        self.popup.addAction("View pathway on KEGG website", self.PopupAction)
        self.popup.addAction("View linked pathway", self.PopupAction)
        
    def SetPathway(self, pathway=None, objects=[]):
##        print 'set pathway',pathway
         
        self.pathway = pathway
        self.objects = objects
        if pathway:
#            self.master.progressBarInit()
            self.image = image = self.pathway.get_image()
#            self.bbDict = self.pathway.get_bounding_box_dict()
            self.graphics_items = [(item, self.pathway.graphics(item)) for item in objects] 
            self.ShowImage()
        else:
            self.bbDict = {}
            self.graphics_items = []
            self.pixmap = None
            self.scene.setSceneRect(QRectF(0, 0, 0, 0))

    def ShowImage(self):
        if self.master.autoResize:
            import Image
            image = Image.open(self.image)
            w, h = image.size
            self.resizeFactor = factor = min(self.width() / float(w), self.height() / float(h))
            resized = image.resize((int(w*factor), int(h*factor)), Image.ANTIALIAS)
            image = os.path.join(obiKEGG.DEFAULT_DATABASE_PATH, "TmpPathwayImage.png")
            resized.save(image)
        else:
            image = self.pathway.get_image()
            self.resizeFactor = 1
        
        self.pixmap = QPixmap(image)
        w, h = self.pixmap.size().width(), self.pixmap.size().height()
        self.scene.setSceneRect(QRectF(0, 0, w, h))
        #self.updateSceneRect(QRectF(self.contentsRect().x(),self.contentsRect().y(),self.contentsRect().width(), self.contentsRect().height()))
        self.updateSceneRect(QRectF(0, 0, w, h))
        
    def getGraphics(self, graphics):
        type, x, y, w, h = graphics.get("type", "rectangle"), graphics.get("x", 0), graphics.get("y", 0), graphics.get("width", 0), graphics.get("height", 0)
        x, y, w, h = [float(c) * self.resizeFactor for c in [x, y, w, h]]
        return type, x, y, w, h

    def drawBackground(self, painter, r):
        QGraphicsView.drawBackground(self, painter, r)
        cx = r.x()
        cy = r.y()
        
        if self.pixmap:
            painter.drawPixmap(0, 0, self.pixmap)
            painter.save()

            painter.setPen(QPen(Qt.blue, 2, Qt.SolidLine))
            painter.setBrush(QBrush(Qt.NoBrush))
            marked_elements = [entry for entry in self.pathway.entrys() if any([object in entry.name for object in self.objects])]
#            for rect in reduce(lambda a,b:a.union(b), [bbList for id, bbList in self.bbDict.items() if id in self.objects], set()):
            
            for element in marked_elements:
                graphics = element.graphics
                type, x, y, w, h = self.getGraphics(graphics)
                if type == "rectangle":
                    painter.drawRect(x - w/2, y - h/2, w, h)
                elif type == "roundrectangle":
                    painter.drawRoundedRect(x - w/2, y - h/2, w, h, 10, 10, Qt.RelativeSize)
                elif type == "circle":
                    painter.drawEllipse(x, y, w, h)
                
            painter.setPen(QPen(Qt.red, 2, Qt.SolidLine))
            for graphics in self.master.selectedObjects.keys(): 
                type, x, y, w, h = self.getGraphics(dict(graphics))
                if type == "rectangle":
                    painter.drawRect(x - w/2, y - h/2, w, h)
                elif type == "roundrectangle":
                    painter.drawRoundedRect(x - w/2, y - h/2, w, h, 10, 10, Qt.RelativeSize)
                elif type == "circle":
                    painter.drawEllipse(x, y, w, h)
                
            painter.restore()
        else:
            painter.drawText(r.center(), "No image available")

    def GetObjects(self, x, y):
        def _in(x, y, graphics):
            type, x1, y1, w, h = self.getGraphics(graphics)
            if type == "rectangle":
                return abs(x1 - x) <= w/2 and abs(y1 - y) <= h/2
            else:
                return abs(x1 - x) <= w and abs(y1 - y) <= h
        point = self.mapToScene(x, y)
        x = point.x()
        y = point.y()

        objs = []
        for id, graphics_list in self.graphics_items:
            for graphics in graphics_list:
                if _in(x, y, graphics):
                    objs.append((id, graphics))
        return objs
    
    def mouseMoveEvent(self, event):
        self.toolTip.maybeTip(event.pos())

    def mousePressEvent(self, event):
        x, y = event.x(), event.y()
        old = set(self.master.selectedObjects.keys())
        objs = self.GetObjects(x, y)
        if event.button() == Qt.LeftButton:
            self.master.SelectObjects([(id, bb) for (id, bb) in objs if id in self.objects])
            for graphics in set(self.master.selectedObjects.keys()).union(old):
#                x1, y1, x2, y2 = map(lambda x:int(self.resizeFactor * x), rect)
                type, x, y, w, h, = self.getGraphics(dict(graphics))
                self.updateScene([QRectF(x - w, y - h, 2 * w, 2 * h)])
        else:
            QGraphicsView.mousePressEvent(self, event)

    def resizeEvent(self, event):
        QGraphicsView.resizeEvent(self, event)
        
        if self.master.autoResize and self.image and self.pathway:
            self.ShowImage()

    def contextMenuEvent(self, event):
        objs = self.GetObjects(event.x(), event.y())
        menu = QMenu(self)
        action = menu.addAction("View pathway on KEGG website")
        self.connect(action, SIGNAL("triggered()"), lambda :self.PopupAction(1, objs))
        if any(id for id, bb in objs if id in self.objects):
            action = menu.addAction("View genes on KEGG website")
            self.connect(action, SIGNAL("triggered()"), lambda :self.PopupAction(0, objs))
        if len(objs)==1 and objs[-1][0].startswith("path:"):
            action = menu.addAction("View linked pathway")
            self.connect(action, SIGNAL("triggered()"), lambda :self.PopupAction(2, objs))
        menu.popup(event.globalPos())

    def PopupAction(self, id, objs):
        import webbrowser
        if id==0:
            genes = [s.split(":")[-1].strip() for s, t in objs if s in self.objects]
            address = "http://www.genome.jp/dbget-bin/www_bget?"+self.pathway.org+"+"+"+".join(genes)
        elif id==1:
##            genes = [s for s, t in self.popup.objs]
##            s = reduce(lambda s,g:s.union(self.master.org.get_enzymes_by_gene(g)), genes, set())
##            address = "http://www.genome.jp/dbget-bin/www_bget?enzyme+"+"+".join([e.split(":")[-1] for e in s])
            genes = [s.split(":")[-1].strip() for s, t in objs if s in self.objects]
            address = "http://www.genome.jp/dbget-bin/show_pathway?"+self.pathway.name.split(":")[-1]+(genes and "+"+"+".join(genes) or "")
        elif id==2:
            self.master.selectedObjects = defaultdict(list)
            self.master.Commit()
            pathway = obiKEGG.KEGGPathway(objs[-1][0])
            pathway.api = self.pathway.api
            self.SetPathway(obiKEGG.KEGGPathway(objs[-1][0]))
            return
        try:
            webbrowser.open(address)
        except Exception, ex:
            print "Failed to open", address, "due to", ex
            pass
    
class OWKEGGPathwayBrowser(OWWidget):
    settingsList = ["organismIndex", "geneAttrIndex", "autoCommit", "autoResize", "useReference", "useAttrNames", "caseSensitive"]
    contextHandlers = {"":DomainContextHandler("",[ContextField("organismIndex", DomainContextHandler.Required + DomainContextHandler.IncludeMetaAttributes),
                                                   ContextField("geneAttrIndex", DomainContextHandler.Required + DomainContextHandler.IncludeMetaAttributes),
                                                   ContextField("useAttrNames", DomainContextHandler.Required + DomainContextHandler.IncludeMetaAttributes)])}
    def __init__(self, parent=None, signalManager=None, name="KEGG Pathway Browser"):
        OWWidget.__init__(self, parent, signalManager, name)
        self.inputs = [("Examples", ExampleTable, self.SetData), ("Reference", ExampleTable, self.SetRefData)]
        self.outputs = [("Selected Examples", ExampleTable), ("Unselected Examples", ExampleTable)]
        self.organismIndex = 0
        self.geneAttrIndex = 0
        self.autoCommit = False
        self.autoResize = True
        self.useReference = False
        self.useAttrNames = 0
        self.caseSensitive = True
        self.showOrthology = True
        self.autoFindBestOrg = False
        self.loadSettings()

        self.controlArea.setMaximumWidth(250)
        self.infoLabel = OWGUI.widgetLabel(OWGUI.widgetBox(self.controlArea, "Info"), "No data on input\n")
        
        self.allOrganismCodes = {} 

        self.organismCodes = []

        self.organismComboBox = cb = OWGUI.comboBox(self.controlArea, self, "organismIndex", box="Organism", items=[], callback=self.Update, addSpace=True, debuggingEnabled=0)
        cb.setMaximumWidth(200)
        
        self.signalManager.setFreeze(1)
        QTimer.singleShot(100, self.UpdateOrganismComboBox)
        
        box = OWGUI.widgetBox(self.controlArea, "Gene attribute")
        self.geneAttrCombo = OWGUI.comboBox(box, self, "geneAttrIndex", callback=self.Update)
        OWGUI.checkBox(box, self, "useAttrNames", "Use variable names", disables=[(-1, self.geneAttrCombo)], callback=self.UseAttrNamesCallback)
        self.geneAttrCombo.setDisabled(bool(self.useAttrNames))
        
        OWGUI.checkBox(box, self, "caseSensitive", "Case sensitive gene matching", callback=self.Update)
        OWGUI.separator(self.controlArea)
        
        OWGUI.checkBox(self.controlArea, self, "useReference", "From signal", box="Reference", callback=self.Update)
        OWGUI.separator(self.controlArea)

        OWGUI.checkBox(self.controlArea, self, "showOrthology", "Show pathways in full orthology", box="Orthology", callback=self.UpdateListView)
        
        OWGUI.checkBox(self.controlArea, self, "autoResize", "Resize to fit", box="Image", callback=lambda :self.pathwayView.image and self.pathwayView.ShowImage())
        OWGUI.separator(self.controlArea)

        box = OWGUI.widgetBox(self.controlArea, "Selection")
        OWGUI.checkBox(box, self, "autoCommit", "Commit on update")
        OWGUI.button(box, self, "Commit", callback=self.Commit)
        OWGUI.rubber(self.controlArea)
        
        spliter = QSplitter(Qt.Vertical, self.mainArea)
        self.pathwayView = PathwayView(self, spliter)
        self.mainArea.layout().addWidget(spliter)

        self.listView = QTreeWidget(spliter)
        spliter.addWidget(self.listView)
        
        self.listView.setAllColumnsShowFocus(1)
        self.listView.setColumnCount(4)
        self.listView.setHeaderLabels(["Pathway", "P value", "Genes", "Reference"])

        self.listView.setSelectionMode(QAbstractItemView.SingleSelection)
            
        self.listView.setSortingEnabled(True)
        #self.listView.setAllColumnsShowFocus(1)
        self.listView.setMaximumHeight(200)
        
        self.connect(self.listView, SIGNAL("itemSelectionChanged()"), self.UpdatePathwayView)
        
        self.ctrlPressed = False
        self.selectedObjects = defaultdict(list)
        self.data = None
        self.refData = None
        self.loadedOrganism = None
        
        self.resize(800, 600)
        
    def UpdateOrganismComboBox(self):
        try:
            self.progressBarInit()
            with orngServerFiles.DownloadProgress.setredirect(self.progressBarSet):
                genome = obiKEGG.KEGGGenome()
            self.progressBarFinished()
            
            self.allOrganismCodes = genome 
    
            essential = genome.essential_organisms()
            
            local = [name.split(".")[0].split("_")[-1] for name in orngServerFiles.listfiles("KEGG") if "kegg_genes" in name]
            self.organismCodes = [(code, organism.definition) for code, organism in self.allOrganismCodes.items() if code in local or code in essential]
            self.organismCodes.sort()
            items = [desc for code, desc in self.organismCodes]
            self.organismCodes = [code for code, desc in self.organismCodes]
            
            self.organismComboBox.addItems(items)
        finally:
            self.signalManager.setFreeze(0)

        
    def SetData(self, data=None):
        self.closeContext()
        self.data = data
        if data:
            self.SetBestGeneAttrAndOrganism()
            taxid = getattr(data, "taxid", None)
            try:
                code = obiKEGG.from_taxid(taxid)
                self.organismIndex = self.organismCodes.index(code)
            except Exception, ex:
                pass
            
            self.useAttrNames = getattr(data, "genesinrows", False)
            
            self.openContext("", data)
            self.Update()
        else:
            self.infoLabel.setText("No data on input\n")
            self.listView.clear()
            self.selectedObjects = defaultdict(list)
            self.pathwayView.SetPathway(None)
            self.send("Selected Examples", None)
            self.send("Unselected Examples", None)

    def SetRefData(self, data=None):
        self.refData = data
        if self.useReference and self.data:
            self.Update()

    def UseAttrNamesCallback(self):
##        self.geneAttrCombo.setDisabled(bool(self.useAttrNames))
        self.Update()

    def SetBestGeneAttrAndOrganism(self):
        self.geneAttrCandidates = self.data.domain.attributes + self.data.domain.getmetas().values()
        self.geneAttrCandidates = filter(lambda v:v.varType in [orange.VarTypes.Discrete ,orange.VarTypes.String], self.geneAttrCandidates)
        self.geneAttrCombo.clear()
        #print 'geneAttrCandidates', self.geneAttrCandidates
        self.geneAttrCombo.addItems([var.name for var in self.geneAttrCandidates])
        data = self.data
        if len(data)>20:
            data = data.select(orange.MakeRandomIndices2(data, 20))
        from cPickle import load
        score = {}
        return
#        self.progressBarInit()
#        with orngServerFiles.DownloadProgress.setredirect(self.progressBarSet):
#            attrNames = [str(v.name).strip() for v in self.data.domain.attributes]
#            testOrgs = self.autoFindBestOrg and self.organismCodes or [self.organismCodes[min(self.organismIndex, len(self.organismCodes)-1)]]
#            for i, org in enumerate(testOrgs):
#                try:
#    ##                print obiKEGG.default_database_path + org + "_genenames.pickle"
#    ##                geneNames = load(open(os.path.join(obiKEGG.default_database_path, org+"_genenames.pickle")))
#                    geneNames = load(self.keggLocalInterface._retrieve(org+"_genenames.pickle", from_="kegg_organism_%s.tar.gz"%org))
#                except Exception, ex:
#    ##                print 'error 2', ex
#                    continue
#                for attr in self.geneAttrCandidates:
#                    vals = [str(e[attr]).strip() for e in data if not e[attr].isSpecial()]
#                    vals = reduce(list.__add__, (split_and_strip(val, ",") for val in vals), [])
#                    match = filter(lambda v:v in geneNames, vals)
#                    score[(attr, org)] = len(match)
#                match = [v for v in attrNames if v in geneNames]
#                score[("_var_names_", org)] = len(match)
#                self.progressBarSet(i*100.0/len(self.organismCodes))
#        self.progressBarFinished()
#        score = [(s, attr, org) for (attr, org), s in score.items()]
#        score.sort()
#        if not score:
#            self.useAttrNames = 1
#            self.geneAttrIndex = min(len(self.geneAttrCandidates)-1, self.geneAttrIndex)
###            self.organismIndex = 0
#        elif score[-1][1]=="_var_names_":
#            self.useAttrNames = 1
#            self.geneAttrIndex = 0 #self.geneAttrCandidates.index(score[-2][1])
#            self.organismIndex = self.organismCodes.index(score[-1][2])
#        else:
#            self.useAttrNames = 0
#            self.geneAttrIndex = self.geneAttrCandidates.index(score[-1][1])
#            self.organismIndex = self.organismCodes.index(score[-1][2])
###        self.geneAttrCombo.setDisabled(bool(self.useAttrNames))
                
                
    def PreDownload(self, org=None, pb=None):
        pb, finish = (OWGUI.ProgressBar(self, 0), True) if pb is None else (pb, False)
        files = ["kegg_brite.tar.gz", "kegg_pathways_map.tar.gz", "kegg_genome.tar.gz"]
        if org:
            files += ["kegg_genes_%s.tar.gz" % org, "kegg_pathways_%s.tar.gz" % org]
        files = [file for file in files if file not in orngServerFiles.listfiles("KEGG")]
        pb.iter += len(files) * 100
        for i, filename in enumerate(files):
            print filename
            orngServerFiles.download("KEGG", filename, callback=pb.advance)
        if finish:
            pb.finish()
            
    def UpdateListView(self):
        self.listView.clear()
        if not self.data:
            return
        allPathways = self.org.pathways()
        allRefPathways = obiKEGG.pathways("map")
        self.progressBarFinished()
        items = []
        if self.showOrthology:
            self.koOrthology = obiKEGG.KEGGBrite("ko00001")
            self.listView.setRootIsDecorated(True)
            path_ids = set([s[-5:] for s in self.pathways.keys()])
            def _walkCollect(koEntry):
                num = koEntry.title[:5] if koEntry.title else None
                if num  in path_ids:
                    return [koEntry] + reduce(lambda li,c:li+_walkCollect(c), [child for child in koEntry.entrys], [])
                else:
                    c = reduce(lambda li,c:li+_walkCollect(c), [child for child in koEntry.entrys], [])
                    return c + (c and [koEntry] or [])
            allClasses = reduce(lambda li1, li2: li1+li2, [_walkCollect(c) for c in self.koOrthology], [])
            def _walkCreate(koEntry, lvItem):
                item = QTreeWidgetItem(lvItem)
                id = "path:"+self.organismCodes[min(self.organismIndex, len(self.organismCodes)-1)] + koEntry.title[:5]
                if koEntry.title[:5] in path_ids:
                    genes, p_value, ref = self.pathways[id]
                    item.setText(0, obiKEGG.KEGGPathway(id).title)
#                    print id, obiKEGG.KEGGPathway(id).title
                    item.setText(1, "%.5f" % p_value)
                    item.setText(2, "%i of %i" %(len(genes), len(self.genes)))
                    item.setText(3, "%i of %i" %(ref, len(self.referenceGenes)))
                    item.pathway_id = id
                else:
                    item.setText(0, obiKEGG.KEGGPathway(id).title if id in allPathways else koEntry.title)
                    if id in allPathways:
                        item.pathway_id = id
                    elif "path:map" + koEntry.title[:5] in allRefPathways:
                        item.pathway_id = "path:map" + koEntry.title[:5]
                    else:
                        item.pathway_id = None
                
                for child in koEntry.entrys:
                    if child in allClasses:
                        _walkCreate(child, item)
            
            for koEntry in self.koOrthology:
                if koEntry in allClasses:
                    _walkCreate(koEntry, self.listView)
                    
            self.listView.update()
        else:
            self.listView.setRootIsDecorated(False)
            pathways = self.pathways.items()
            pathways.sort(lambda a,b:cmp(a[1][1], b[1][1]))
            for id, (genes, p_value, ref) in pathways:
                item = QTreeWidgetItem(self.listView)
                item.setText(0, obiKEGG.KEGGPathway(id).title)
                item.setText(1, "%.5f" % p_value)
                item.setText(2, "%i of %i" %(len(genes), len(self.genes)))
                item.setText(3, "%i of %i" %(ref, len(self.referenceGenes)))
                item.pathway_id = id
                items.append(item)
                
        self.bestPValueItem = items and items[0] or None
        self.listView.expandAll()
        for i in range(4):
            self.listView.resizeColumnToContents(i)

    def UpdatePathwayView(self):
        items = self.listView.selectedItems()
        
        if len(items) > 0:
            item = items[0]
            
            self.selectedObjects = defaultdict(list)
            self.Commit()
            item = item or self.bestPValueItem
            if not item or not item.pathway_id:
                self.pathwayView.SetPathway(None)
                return
            self.pathway = obiKEGG.KEGGPathway(item.pathway_id)
            self.pathwayView.SetPathway(self.pathway, self.pathways.get(item.pathway_id, [[]])[0])
            
    def Update(self):
        if not self.data:
            return
        self.error(0)
        self.information(0)
        pb = OWGUI.ProgressBar(self, 100)
        if self.useAttrNames:
            genes = [str(v.name).strip() for v in self.data.domain.attributes]
        elif self.geneAttrCandidates:
            geneAttr = self.geneAttrCandidates[min(self.geneAttrIndex, len(self.geneAttrCandidates)-1)]
            genes = [str(e[geneAttr]) for e in self.data if not e[geneAttr].isSpecial()]
            if any("," in gene for gene in genes):
                genes = reduce(list.__add__, (split_and_strip(gene, ",") for gene in genes), [])
                self.information(0, "Separators detected in input gene names. Assuming multiple genes per example.")
        else:
            self.error(0, "Cannot extact gene names from input")
            genes = []
        org_code = self.organismCodes[min(self.organismIndex, len(self.organismCodes)-1)]
        if self.loadedOrganism != org_code:
            self.PreDownload(org_code, pb=pb)
            self.org = obiKEGG.KEGGOrganism(org_code)
            self.loadedOrganism = org_code
        uniqueGenes, conflicting, unknown = self.org.get_unique_gene_ids(set(genes), self.caseSensitive)
        self.infoLabel.setText("%i genes on input\n%i (%.1f%%) genes matched" % (len(genes), len(uniqueGenes), 100.0*len(uniqueGenes)/len(genes) if genes else 0.0))  
        if conflicting:
            print "Conflicting genes:", conflicting
        if unknown:
            print "Unknown genes:", unknown
        self.information(1)
        if self.useReference and self.refData:
            if self.useAttrNames:
                reference = [str(v.name).strip() for v in self.refData]
            else:
                geneAttr = self.geneAttrCandidates[min(self.geneAttrIndex, len(self.geneAttrCandidates)-1)]
                reference = [str(e[geneAttr]) for e in self.refData if not e[geneAttr].isSpecial()]
                if any("," in gene for gene in reference):
                    reference = reduce(list.__add__, (split_and_strip(gene, ",") for gene in reference), [])
                    self.information(1, "Separators detected in reference gene names. Assuming multiple genes per example.")
            uniqueRefGenes, conflicting, unknown = self.org.get_unique_gene_ids(set(reference), self.caseSensitive)
            self.referenceGenes = reference = uniqueRefGenes.keys()
        else:
            self.referenceGenes = reference = self.org.get_genes()
        self.uniqueGenesDict = uniqueGenes
        self.genes = uniqueGenes.keys()
        self.revUniqueGenesDict = dict([(val, key) for key, val in self.uniqueGenesDict.items()])
#        self.progressBarInit()
#        with orngServerFiles.DownloadProgress.setredirect(self.progressBarSet):
        self.pathways = self.org.get_enriched_pathways(self.genes, reference, callback=lambda value: pb.advance()) #self.progressBarSet)
#        self.progressBarFinished()
        self.UpdateListView()
        pb.finish()
##        print self.bestPValueItem
        #self.bestPValueItem.setSelected(True)
        #self.UpdatePathwayView()

    def SelectObjects(self, objs):
        if (not self.selectedObjects or self.ctrlPressed) and not objs:
            return
        if self.ctrlPressed:
            for id, graphics in objs:
                graphics = tuple(sorted(graphics.items()))
                if id in self.selectedObjects[graphics]:
                    self.selectedObjects[graphics].pop(self.selectedObjects[graphics].index(id))
                    if not self.selectedObjects[graphics]:
                        del self.selectedObjects[graphics]
                else:
                    self.selectedObjects[graphics].append(id)
        else:
            self.selectedObjects.clear()
            for id, graphics in objs:
                graphics = tuple(sorted(graphics.items()))
                self.selectedObjects[graphics].append(id)
        if self.autoCommit:
            self.Commit()
            

    def Commit(self):
        def passAttributes(src, dst, names):
            for name in names:
                if hasattr(src, name):
                    setattr(dst, name, getattr(src, name))
        if self.data:
            if self.useAttrNames:
                selectedGenes = reduce(set.union, self.selectedObjects.values(), set())
                selectedVars = [self.data.domain[self.uniqueGenesDict[gene]] for gene in selectedGenes]
                newDomain = orange.Domain(selectedVars ,0)
                data = orange.ExampleTable(newDomain, self.data)
                passAttributes(self.data, data, ["taxid", "genesinrows"])
                self.send("Selected Examples", data)
            else:
                geneAttr = self.geneAttrCandidates[min(self.geneAttrIndex, len(self.geneAttrCandidates)-1)]
                selectedExamples = []
                otherExamples = []
                selectedGenes = reduce(set.union, self.selectedObjects.values(), set())
                for ex in self.data:
                    names = [self.revUniqueGenesDict.get(name, None) for name in split_and_strip(str(ex[geneAttr]), ",")]
                    if any(name and name in selectedGenes for name in names):
                        selectedExamples.append(ex)
                    else:
                        otherExamples.append(ex)
                        
                if selectedExamples:
                    selectedExamples = orange.ExampleTable(selectedExamples)
                    passAttributes(self.data, selectedExamples, ["taxid", "genesinrows"])
                else:
                    selectedExamples = None
                    
                if otherExamples:
                    otherExamples = orange.ExampleTable(otherExamples)
                    passAttributes(self.data, otherExamples, ["taxid", "genesinrows"])
                else:
                    otherExamples = None
                    
                self.send("Selected Examples", selectedExamples)
                self.send("Unselected Examples", otherExamples)
        else:
            self.send("Selected Examples", None)
            self.send("Unselected Examples", None)
        
    def keyPressEvent(self, key):
        if key.key()==Qt.Key_Control:
            self.ctrlPressed=True
        else:
            OWWidget.keyPressEvent(self, key)

    def keyReleaseEvent(self, key):
        if key.key()==Qt.Key_Control:
            self.ctrlPressed=False
        else:
            OWWidget.keyReleaseEvent(self, key)

if __name__=="__main__":
    app = QApplication(sys.argv)
    data = orange.ExampleTable("../../../../orange/doc/datasets/brown-selected.tab")
    w = OWKEGGPathwayBrowser()
##    app.setMainWidget(w)
    w.show()
    w.SetData(data)
    app.exec_()
    w.saveSettings()
