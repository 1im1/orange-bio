"""\
Protein-protein interactions
============================

This is python module for accessing PPI data.  
"""

import os, sys
import xml.dom.minidom as minidom
import warnings
import collections

import orngServerFiles

from obiKEGG import downloader

from collections import defaultdict

import obiTaxonomy
from obiTaxonomy import pickled_cache

from Orange.misc import lru_cache

import sqlite3
import urllib2
import posixpath
import shutil

class PPIDatabase(object):
    """ A general interface for protein-protein interaction database access.
    
    An example useage::
        >>> ppidb = MySuperPPIDatabase()
        >>> ppidb.organisms() # List all organisms (taxids)
        ['...
        
        >>> ppidb.ids() # List all protein ids
        ['...
        
        >>> ppidb.ids(taxid="9606") # List all human protein ids.
        ['...
        
        >>> ppidb.links() # List all links 
        [('...
    """
    def __init__(self):
        pass
    
    def organisms(self):
        """ Return all organism taxids contained in this database.
        """
        raise NotImplementedError
    
    def ids(self, taxid=None):
        """ Return a list of all protein ids. If `taxid` is not None limit
        the results to ids from this organism only.
        
        """
        raise NotImplementedError
    
    def synonyms(self, id):
        """ Return a list of synonyms for primary `id`.
        """
        raise NotImplementedError
    
    def all_edges(self, taxid=None):
        """ Return a list of all edges. If taxid is not None return the
        edges for this organism only. 
        
        """
        raise NotImplementedError
    
    def edges(self, id1, id2=None):
        """ Return a list of all edges (a list of 3-tuples (id1, id2, score)).
        """
        raise NotImplementedError
        
    def edges_annotated(self, id=None):
        """ Return a list of all edges annotated
        """
        raise NotImplementedError
     
    def search_id(self, name, taxid=None):
        """ Search the database for protein name. Return a list of matching 
        primary ids. Use `taxid` to limit the results to a single organism.
         
        """
        raise NotImplementedError
    
    @classmethod
    def download_data(self):
        """ Download the latest PPI data for local work.
        """
        raise NotImplementedError
    
class BioGRID(PPIDatabase):
    """ Access `BioGRID <http://thebiogrid.org>`_ PPI data.
    
    Example ::
    
        >>> biogrid = BioGRID()
        >>> print biogrid.organism() # Print a list of all organism ncbi taxis in BioGRID
        [u'10090',...
        
        >>> print biogrid.ids(taxid="9606") # Print a set of all human protein ids
        [u'110004'
        
        >>> print biogrid.synonyms("110004") # Print a list of all synonyms for protein id '110004' as reported by BioGRID
        [u'3803', u'CU464060.2', u'CD158b', u'p58.2', u'CD158B1', u'NKAT6']
        
        >>> 
        
    """
    
    SCHEMA = [("links", """\
        biogrid_interaction_id text, 
        biogrid_id_interactor_a text,
        biogrid_id_interactor_b text,
        experimental_system text,
        experimental_system_type text,
        author text,
        pubmed_id text,
        throughput text,
        score real,
        modification text,
        phenotypes text,
        qualifications text,
        tags text,
        source_database text
        """),
            ("proteins", """\
        biogrid_id_interactor text,
        entrez_gene_interactor text,
        systematic_name_interactor text,
        official_symbol_interactor text,
        synonyms_interactor text,
        organism_interactor text,
        """)]
    VERSION = "2.0"
    
    # All column names in the tab2 table. 
    FIELDS = ['biogrid_interaction_id',
              'entrez_gene_interactor_a',
              'entrez_gene_interactor_b',
              'biogrid_id_interactor_a',
              'biogrid_id_interactor_b',
              'systematic_name_interactor_a',
              'systematic_name_interactor_b',
              'official_symbol_interactor_a',
              'official_symbol_interactor_b',
              'synonyms_interactor_a',
              'synonyms_interactor_b',
              'experimental_system',
              'experimental_system_type',
              'author',
              'pubmed_id',
              'organism_interactor_a',
              'organism_interactor_b',
              'throughput',
              'score',
              'modification',
              'phenotypes',
              'qualifications',
              'tags',
              'source_database'
              ]
    
#    BioGRIDInteraction = collections.namedtuple("BioGRIDInteraction", " ".join(SCHEMA[0][1]))
#    BioGRIDInteractor = collections.namedtuple("BioGRIDInteractor", " ".join(SCHEMA[1][1]))
    
    DOMAIN = "PPI"
    SERVER_FILE = "BIOGRID-ALL.sqlite"
    
    def __init__(self):
        self.filename = orngServerFiles.localpath_download(self.DOMAIN, self.SERVER_FILE)
#        info = orngServerFiles.info(self.DOMAIN, self.SERVER_FILE)
        # assert version matches
        self.db = sqlite3.connect(self.filename)
        self.init_db_index()

    @lru_cache(1)
    def organisms(self):
        cur = self.db.execute("select distinct organism_interactor from proteins")
        return cur.fetchall()

    @lru_cache(3)
    def ids(self, taxid=None):
        """ Return a list of all protein ids (biogrid_id_interactors).
        If `taxid` is not None limit the results to ids from this organism
        only.
        
        """
        if taxid is None:
            cur = self.db.execute("""\
                select biogrid_id_interactor
                from proteins""")
        else:
            cur = self.db.execute("""\
                select biogrid_id_interactor
                from proteins
                where organism_interactor=?""", (taxid,))
        
        return [t[0] for t in cur.fetchall()]

    def synonyms(self, id):
        """ Return a list of synonyms for primary `id`.
        
        """
        cur = self.db.execute("""\
            select entrez_gene_interactor,
                   systematic_name_interactor,
                   official_symbol_interactor,
                   synonyms_interactor
            from proteins
            where biogrid_id_interactor=?
            """, (id,))
        rec = cur.fetchone()
        synonyms = list(rec[:-1]) + (rec[-1].split("|") if rec[-1] is not None else [])
        return [s for s in synonyms if s is not None]
    
    def all_edges(self, taxid=None):
        """ Return a list of all edges. If taxid is not None return the
        edges for this organism only. 
        
        """
        if taxid is not None:
            cur = self.db.execute("""\
                select biogrid_id_interactor_a, biogrid_id_interactor_a, score
                from links left join proteins on 
                    biogrid_id_interactor_a=biogrid_id_interactor or
                    biogrid_id_interactor_b=biogrid_id_interactor
                where organism_interactor=?
            """, (taxid,))
        else:
            cur = self.db.execute("""\
                select biogrid_id_interactor_a, biogrid_id_interactor_a, score
                from links
            """)
        edges = cur.fetchall()
        return edges
            
    def edges(self, id):
        """ Return a list of all interactions where id is a participant
        (a list of 3-tuples (id_a, id_b, score)).
        
        """
        
        cur = self.db.execute("""\
            select biogrid_id_interactor_a, biogrid_id_interactor_b, score
            from links
            where biogrid_id_interactor_a=? or biogrid_id_interactor_b=?
        """, (id, id))
        return cur.fetchall() 
        
        
    def edges_annotated(self, id):
        """ Return a list of all links
        """
        cur = self.db.execute("""\
            select *
            from links
            where biogrid_id_interactor_a=? or biogrid_id_interactor_b=?
        """, (id, id))
        return cur.fetchall()
    
    def search_id(self, name, taxid=None):
        """ Search the database for protein name. Return a list of matching 
        primary ids. Use `taxid` to limit the results to a single organism.
         
        """
        if taxid is None:
            self.db.execute("""\
                select biogrid_id_interactor
                from proteins
                where biogrid_id_interactor=? or
                      entrez_id_interactor=? or
                      systematic_name_interactor=? or
                      official_symbol_interactor=? or
                      synonyms_interactor=?
            """ (id,) * 5)
    
    @classmethod
    def download_data(cls, address):
        """ Pass the address of the latest release (the tab2 format).
        """
        import urllib2, shutil, zipfile
        from StringIO import StringIO
        stream = urllib2.urlopen(address)
        stream = StringIO(stream.read())
        file = zipfile.ZipFile(stream)
        filename = file.namelist()[0]
        ppi_dir = orngServerFiles.localpath("PPI")
        file.extract(filename, ppi_dir)
        shutil.move(orngServerFiles.localpath("PPI", filename),
                    orngServerFiles.localpath("PPI", "BIOGRID-ALL.tab2"))
        filepath = orngServerFiles.localpath("PPI", "BIOGRID-ALL.tab2")
        cls.init_db(filepath)
        shutil.remove(filepath)
        
    @classmethod
    def init_db(cls, filepath):
        """ Initialize the sqlite data base from a BIOGRID-ALL.*tab2.txt file
        format.
        
        """
        dirname = os.path.dirname(filepath)
        lineiter = iter(open(filepath, "rb"))
        headers = lineiter.next() # read the first line
        
        con = sqlite3.connect(os.path.join(dirname, "BIOGRID-ALL.sqlite"))
        con.execute("drop table if exists links") # Drop old table
        con.execute("drop table if exists proteins") # Drop old table
        
        con.execute("""\
            create table links (
                biogrid_interaction_id text, 
                biogrid_id_interactor_a text,
                biogrid_id_interactor_b text,
                experimental_system text,
                experimental_system_type text,
                author text,
                pubmed_id text,
                throughput text,
                score real,
                modification text,
                phenotypes text,
                qualifications text,
                tags text,
                source_database text
            )""")
        
        con.execute("""\
            create table proteins (
                biogrid_id_interactor text,
                entrez_gene_interactor text,
                systematic_name_interactor text,
                official_symbol_interactor text,
                synonyms_interactor text,
                organism_interactor text
            )""")
        
        proteins = {}
        nulls = lambda values: [val if val != "-" else None for val in values]
        link_indices = [0, 3, 4, 11, 12, 13, 14, 17, 18, 19, 20, 21, 22, 23] # Values that go in the links table
        interactor_a_indices = [3, 1, 5, 7, 9, 15] # Values that go in the proteins table
        interactor_b_indices = [4, 2, 6, 8, 10, 16] # Values that go in the proteins table
        
        def processlinks(file):
            for line in file:
                if line != "\n":
                    fields = nulls(line.strip().split("\t"))
                    yield [fields[i] for i in link_indices]
                    interactor_a = [fields[i] for i in interactor_a_indices]
                    interactor_b = [fields[i] for i in interactor_b_indices]
                    proteins[interactor_a[0]] = interactor_a
                    proteins[interactor_b[0]] = interactor_b
        
        con.executemany("""\
            insert into links values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, processlinks(lineiter))
        
        con.executemany("""\
            insert into proteins values (?, ?, ?, ?, ?, ?)
            """, proteins.itervalues())
        con.commit()
        con.close()
        
    def init_db_index(self):
        """ Will create an indexes (if not already pressent) in the database
        for faster searching by primary ids.
        
        """
        self.db.execute("""\
        create index if not exists index_on_biogrid_id_interactor_a
           on links (biogrid_id_interactor_a)
        """)
        self.db.execute("""\
        create index if not exists index_on_biogrid_id_interactor_b
           on links (biogrid_id_interactor_b)
        """)
        self.db.execute("""\
        create index if not exists index_on_biogrid_id_interactor
           on proteins (biogrid_id_interactor)
        """)
        
    
class STRING(PPIDatabase):
    """ Access `STRING <http://www.string-db.org/>`_ PPI database.
    
    Database schema
    ---------------
    table `links`:
        - `protein_id1`: id (text)
        - `protein_id2`: id (text)
        - `score`: combined score (int)
        
    table `actions`:
        - `protein_id1`: id (text)
        - `protein_id2`: id (text)
        - `mode`: mode (text)
        - `action`: action type (text)
        - `score`: action score (int)
        
    table `proteins`:
        - `protein_id`: protein id in STRING (text) (in the form of {taxid}.{name})
        - `taxid`: organism taxid (text)
        
    table `aliases`:
        - `protein_id: id (text)
        - `alias`: protein alias (text) 
        
    """
    DOMAIN = "PPI"
    FILENAME = "string-protein.sqlite"
    VERSION = "1.0"
    
    def __init__(self):
        self.filename = orngServerFiles.localpath_download(self.DOMAIN, self.FILENAME)
        self.db = sqlite3.connect(self.filename)
        self.init_db_index()
        
    def organisms(self):
        """ Return all organism taxids contained in this database.
        """
        cur = self.db.execute("select distinct taxid from proteins")
        return [r[0] for r in cur.fetchall()]
    
    def ids(self, taxid=None):
        """ Return a list of all protein ids. If `taxid` is not None limit
        the results to ids from this organism only.
        
        """
        if taxid is not None:
            cur = self.db.execute("""\
                select protein_id
                from proteins
                where taxid=?
                """, (taxid,))
        else:
            cur = self.db.execute("""\
                select protein_id
                from proteins
                """)
        return [r[0] for r in cur.fetchall()]
    
    def synonyms(self, id):
        """ Return a list of synonyms for primary `id` as reported by STRING (proteins.aliases.{version}.txt file)
        """
        cur = self.db.execute("""\
            select alias
            from aliases
            where protein_id=?
            """, (id,))
        res = cur.fetchall()
        return [r[0] for r in res]
    
    def all_edges(self, taxid=None):
        """ Return a list of all edges. If taxid is not None return the
        edges for this organism only.
        
        .. note:: This may take some time (and memory).
        
        """
        if taxid is not None:
            cur = self.db.execute("""\
                select links.protein_id1, links.protein_id2, score
                from links join proteins on
                    links.protein_id1=proteins.protein_id
                where taxid=?
                """, (taxid,))
        else:
            cur = self.db.execute("""\
                select protein_id1, protein_id1, score
                from links
                """)
        return cur.fetchall()
        
    def edges(self, id):
        """ Return a list of all edges (a list of 3-tuples (id1, id2, score)).
        """
        cur = self.db.execute("""\
            select protein_id1, protein_id2, score
            from links
            where protein_id1=?
            """, (id,))
        return cur.fetchall()
        
    def edges_annotated(self, id):
        """ Return a list of all links
        """
        raise NotImplementedError
    
    @classmethod
    def download_data(cls, version, taxids=None):
        """ Download the  PPI data for local work (this may take some time).
        Pass the version of the  STRING release e.g. v8.3.
        The resulting sqlite database will only contain the protein
        interactions for `taxids` (if None all interactions will be present).
        
        """
        dir = orngServerFiles.localpath("PPI")
        
        def download(address, dir):
            stream = urllib2.urlopen(address)
            basename = posixpath.basename(address)
            tmpfilename = os.path.join(dir, basename + ".part")
            tmpfile = open(tmpfilename, "wb")
            shutil.copyfileobj(stream, tmpfile)
            tmpfile.close()
            os.rename(tmpfilename, basename)
        base_url = "http://www.string-db.org/newstring_download/" #protein.links.v9.0.txt.gz
        links = base_url + "protein.links.{version}.txt.gz"
        actions = base_url + "protein.actions.{version}.txt.gz"
        aliases = base_url + "protein.aliases.{version}.txt.gz"
        
        download(links.format(version=version), dir)
        download(actions.format(version=version), dir)
        download(aliases.format(version=version), dir)
        
        links_filename = os.path.join(dir, "protein.links.{version}.txt".format(version=version))
        actions_filename = os.path.join(dir, "protein.links.{version}.txt".format(version=version))
        aliases_filename = os.path.join(dir, "protein.aliases.{version}.txt".format(version=version))
        
        from orngMisc import ConsoleProgressBar
        
        progress = ConsoleProgressBar("Extracting files:")
        progress(1.0)
        links_file = gzip.GzipFile(links_filename + ".gz", "rb")
        shutil.copyfileobj(links_file, open(links_filename, "wb"))
        
        progress(60.0)
        actions_file = gzip.GzipFile(actions_filename + ".gz", "rb")
        shutil.copyfileobj(actions_file, open(actions_filename, "wb"))
        actions_file = open(actions_filename, "rb")
#        
        progress(90.0)
        aliases_file = gzip.GzipFile(aliases_filename + ".gz", "rb")
        shutil.copyfileobj(aliases_file, open(aliases_filename, "wb"))
        aliases_file = open(aliases_filename, "rb")
        progress.finish()
        
        cls.init_db(version, taxids)
        
    @classmethod
    def init_db(cls, version, taxids=None):
        """ Initialize the sqlite3 data base. `version` must contain a
        STRING release version e.g 'v8.3'. If `taxids` is not `None` it
        must contain a list of tax-ids in the STRING database for which
        to extract the interactions for.
        
        """
        def counter():
            i = 0
            while True:
                yield i
                i += 1
                
        protein_ids = defaultdict(counter().next)
        protein_taxid = {}

        dir = orngServerFiles.localpath(cls.DOMAIN)
        
        links_filename = os.path.join(dir, "protein.links.{version}.txt".format(version=version))
        actions_filename = os.path.join(dir, "protein.actions.{version}.txt".format(version=version))
        aliases_filename = os.path.join(dir, "protein.aliases.{version}.txt".format(version=version))
        
        links_file = open(links_filename, "rb")
        actions_file = open(actions_filename, "rb")
        aliases_file = open(aliases_filename, "rb")
        
        from orngMisc import ConsoleProgressBar
        
        progress = ConsoleProgressBar("Processing links file:")
        progress(0.0)
        filesize = os.stat(links_filename).st_size
        
        taxids = set(taxids) if taxids else set(obiTaxonomy.common_taxids())
                
        con = sqlite3.connect(orngServerFiles.localpath(cls.DOMAIN, cls.FILENAME))
        
        con.execute("drop table if exists links")
        con.execute("drop table if exists proteins")
        con.execute("drop table if exists actions")
        con.execute("drop table if exists aliases")
        
        con.execute("create table links (protein_id1 text, protein_id2 text, score int)")
        con.execute("create table proteins (protein_id text, taxid text)")
        con.execute("create table actions (protein_id1 text, protein_id2 text, mode text, action text, score int)")
        con.execute("create table aliases (protein_id text, alias text)")
        
        header = links_file.readline() # read the header
        
        import csv
        reader = csv.reader(links_file, delimiter=" ")
        
        def read_links(reader):
            links = []
            i = 0
            for p1, p2, score in reader:
                taxid1 = p1.split(".", 1)[0]
                taxid2 = p2.split(".", 1)[0]
                if taxid1 in taxids and taxid2 in taxids:
                    links.append((intern(p1), intern(p2), int(score)))
                i += 1
                if i % 1000 == 0: # Update the progress every 1000 lines
                    progress(100.0 * links_file.tell() / filesize)
            links.sort()
            return links
        
        con.executemany("insert into links values (?, ?, ?)", read_links(reader))
            
        con.commit()
        
        progress.finish()
        
        proteins = [res[0] for res in con.execute("select distinct protein_id1 from links")]
        progress = ConsoleProgressBar("Processing proteins:")
        
        def protein_taxids(proteins):
            protein_taxids = []
            for i, prot in enumerate(proteins):
                taxid = prot.split(".", 1)[0]
                protein_taxids.append((prot, taxid))
                if i % 1000 == 0:
                    progress(100.0 * i / len(proteins))
            protein_taxids.sort()
            return protein_taxids
        
        con.executemany("insert into proteins values (?, ?)", protein_taxids(proteins))

        con.commit()
        progress.finish()
        
        filesize = os.stat(actions_filename).st_size
        
        actions_file.readline() # read header
        
        progress = ConsoleProgressBar("Processing actions:")
        reader = csv.reader(actions_file, delimiter="\t")
        def read_actions(reader):
            actions = []
            i = 0
            for p1, p2, mode, action, a_is_acting, score in reader:
                taxid1 = p1.split(".", 1)[0]
                taxid2 = p2.split(".", 1)[0]
                if taxid1 in taxids and taxid2 in taxids:
                    actions.append((intern(p1), intern(p2), mode, action, int(score)))
                i += 1
                if i % 1000 == 0:
                    progress(100.0 * actions_file.tell() / filesize)
            actions.sort()
            return actions
        
        con.executemany("insert into actions values (?, ?, ?, ?, ?)", read_actions(reader))
        con.commit()
        progress.finish()
        
        filesize = os.stat(aliases_filename).st_size
        aliases_file.readline() # read header
        
        progress = ConsoleProgressBar("Processing aliases:")
                        
        reader = csv.reader(aliases_file, delimiter="\t")
        def read_aliases(reader):
            i = 0
            for taxid, name, alias, source in reader:
                if taxid in taxids:
                    yield ".".join([taxid, name]), alias
                i += 1
                if i % 1000 == 0:
                    progress(100.0 * aliases_file.tell() / filesize)
                    
        con.executemany("insert into aliases values (?, ?)", read_aliases(reader))
        con.commit()
        progress.finish()
        
    def init_db_index(self):
        """ Will create indexes (if not already pressent) in the database
        for faster searching by primary ids.
        
        """
        self.db.execute("""\
            create index if not exists index_link_protein_id1
                on links (protein_id1)""")
        
        self.db.execute("""\
            create index if not exists index_action_protein_id1
                on actions (protein_id1)""")
        
        self.db.execute("""\
            create index if not exists index_proteins_id
                on proteins (protein_id)""")
        
        self.db.execute("""\
            create index if not exists index_taxids
                on proteins (taxid)""")
        
        self.db.execute("""\
            create index if not exists index_aliases_id
                on aliases (protein_id)""")
        
        self.db.execute("""\
            create index if not exists index_aliases_alias
                on aliases (alias)""")
        
        
class Interaction(object):
    def __init__(self, protein1, protein2, ref1=None, ref2=None, conf1=None, conf2=None):
        self.protein1, self.protein2 = protein1, protein2
        self.ref1, self.ref2 = ref1, ref2
        self.conf1, self.conf2 = conf1, conf2
        self.org1, self.org2 = None, None
    
class MIPS(object):
    VERSION = 1
    def __init__(self):
        self.load()
        
    def load(self):
        self.protein_names = defaultdict(set)
        self.refs = {}
        self.confidance = {}
        def process(element):
            d = {}
            participants = element.getElementsByTagName("proteinParticipant")
            proteins = []
            for protein in participants:
                interactor = protein.getElementsByTagName("proteinInteractor")[0]
                names = []
                for name in interactor.getElementsByTagName("shortLabel") + \
                            interactor.getElementsByTagName("fullName"):
                    names.append((name.tagName, name.childNodes[0].data))
                
                refs = []
                for ref in interactor.getElementsByTagName("primaryRef"):
                    refs += [(ref.tagName, ref.attributes.items())]
                org = dict(interactor.getElementsByTagName("organism")[0].attributes.items()).get("ncbiTaxId")
                conf = protein.getElementsByTagName("confidence")[0].attributes.items()
                proteins.append((names, refs, conf, org))
            interaction = Interaction(proteins[0][0][1][1], proteins[1][0][1][1])
            interaction.ref1, interaction.ref2 = proteins[0][1], proteins[1][1]
            interaction.conf1, interaction.conf2 = proteins[0][2], proteins[1][2]
            interaction.org1, interaction.org2 = proteins[0][3], proteins[1][3]
            
            self.protein_names[interaction.protein1].add(proteins[0][0][0][1])
            self.protein_names[interaction.protein2].add(proteins[1][0][0][1])
            
            return interaction 
            
        document = minidom.parse(orngServerFiles.localpath_download("PPI", "allppis.xml"))
        interactions = document.getElementsByTagName("interaction")
        self.interactions = [process(interaction) for interaction in interactions]
        
        self.protein_interactions = defaultdict(set)
        
        for inter in self.interactions:
            self.protein_names[inter.protein1] = dict(inter.ref1[0][1]).get("id")
            self.protein_names[inter.protein2] = dict(inter.ref2[0][1]).get("id")
            self.protein_interactions[inter.protein1].add(inter)
            self.protein_interactions[inter.protein2].add(inter) 
       
    def __iter__(self):
        return iter(self.interactions)
    
    @classmethod
    def download(cls):
        import urllib2, shutil
        src = urllib2.urlopen("http://mips.helmholtz-muenchen.de/proj/ppi/data/mppi.gz")
        dest = orngServerFiles.localpath("PPI", "mppi.gz")
        shutil.copyfileobj(src, open(dest, "wb"))
       
    @classmethod 
    @pickled_cache(None, [("PPI", "allppis.xml")], version=1)
    def _get_instance(cls):
        return MIPS()
    
    @classmethod
    def get_instance(cls):
        if not hasattr(cls, "_instance"):
            cls._instance= cls._get_instance()
        return cls._instance
    
def mips_interactions(protein = None):
    mips = MIPS.get_instance()
    if protein is None:
        return list(mips)
    else:
        return mips.protein_interactions.get(protein)

def mips_proteins():
    return set(MIPS.get_instance().protein_names.keys())

class BioGRIDInteraction(object):
    """ An object representing a BioGRID interaction. Each member of this object
    represents a data from a single column of BIOGRID-ALL.tab file.
    Attributes:
        - *interactor_a*    - BioGRID identifier
        - *interactor_b*    - BioGRID identifier
        - *official_symbol_a*    - An official symbol for *interactor_a*
        - *official_symbol_b*    - An official symbol for *interactor_b*
        - *aliases_for_a*    - Aliases separated by '|'
        - *aliases_for_b*    - Aliases separated by '|'
        - *experimental_system*     - Experimental system (see BioGRID documentation on www.thebiogrid.org for a list of valid entrys)
        - *source*    - 
        - *organism_a_id*    - NCBI Taxonomy identifier for *interactor_a*'s organism
        - *organism_b_id*    - NCBI Taxonomy identifier for *interactor_b*'s organism
    """
    __slots__ = ["interactor_a", "interactor_b", "official_symbol_a","official_symbol_b", "aliases_for_a", "aliases_for_b", "experimental_system", "source", "pubmed_id", "organism_a_id", "organism_b_id"]
    def __init__(self, line):
        for attr, val in zip(self.__slots__, line.split("\t")):
            setattr(self, attr, val)

class _BioGRID_Old(object):
    """ A BioGRID database interface
    Example::
        >>> ## finding all interactions for Homo sapiens sapiens
        >>> grid = BioGRID(case_insensitive=True)
        >>> proteins = proteins = biogrid.proteins() ## All proteins
        >>> proteins = [p for p in proteins if any(["9606" in [int.organism_a_id, int.organism_b_id] for int in grid.get(p)])]
    """
    VERSION = 1
    def __init__(self, case_insensitive=True):
#        warnings.warn("obiPPi._BioGRID_Old class is deprecated. Use obiPPI.BioGRID")
        self.case_insensitive = case_insensitive
        self._case = (lambda name: name.lower()) if self.case_insensitive else (lambda name: name)
        self.load()
        
    def load(self):
        text = open(orngServerFiles.localpath_download("PPI", "BIOGRID-ALL.tab"), "rb").read()
        text = text.split("SOURCE\tPUBMED_ID\tORGANISM_A_ID\tORGANISM_B_ID\n", 1)[-1]
        self.interactions = [BioGRIDInteraction(line) for line in text.split("\n") if line.strip()]
        
        self.protein_interactions = defaultdict(set)
        self.protein_names = {}
        
        case = self._case

        def update(keys, value, collection):
            for k in keys:
                collection.setdefault(k, set()).add(value)
                
        for inter in self.interactions:
            update(map(case, [inter.official_symbol_a] + inter.aliases_for_a.split("|")), case(inter.interactor_a), self.protein_names)
            update(map(case, [inter.official_symbol_b] + inter.aliases_for_b.split("|")), case(inter.interactor_b), self.protein_names)
            
            self.protein_interactions[case(inter.interactor_a)].add(inter)
            self.protein_interactions[case(inter.interactor_b)].add(inter)
            
        self.protein_interactions = dict(self.protein_interactions)

        if case("N/A") in self.protein_names:
            del self.protein_names[case("N/A")]
        
    def proteins(self):
        """ Return all protein names in BioGRID (from INTERACTOR_A, and INTERACTOR_B columns) 
        """
        return self.protein_interactions.keys()
            
    def __iter__(self):
        """ Iterate over all BioGRIDInteraction objects
        """
        return iter(self.interactions)
    
    def __getitem__(self, key):
        """ Return a list of protein interactions that a protein is a part of 
        """
        key = self._case(key)
#        keys = self.protein_alias_matcher.match(key)
        if key not in self.protein_interactions:
            keys = self.protein_names.get(key, [])
        else:
            keys = [key]
        if keys:
            return list(reduce(set.union, [self.protein_interactions.get(k, []) for k in keys], set()))
        else:
            raise KeyError(key)
    
    def get(self, key, default=None):
        """ Return a list of protein interactions that a protein is a part of
        """
        key = self._case(key)
#        keys = self.protein_alias_matcher.match(key)
        if key not in self.protein_interactions:
            keys = self.protein_names.get(keys, [])
        else:
            keys = [key] 
        if keys:
            return list(reduce(set.union, [self.protein_interactions.get(k, []) for k in keys], set()))
        else:
            return default
        
    @classmethod
    def get_instance(cls):
        if getattr(cls, "_instance", None) is None:
            cls._instance = _BioGRID_Old()
        return cls._instance
    
def biogrid_interactions(name=None):
    """Return a list of protein interactions (BioGRIDInteraction objects) that a protein is a part of
    """ 
    if name:
        return list(_BioGRID_Old.get_instance().get(name, set()))
    else:
        return _BioGRID_Old.get_instance().interactions
    
def biogrid_proteins():
    """ Return all protein names in BioGRID (from INTERACTOR_A, and INTERACTOR_B columns)
    """
    return _BioGRID_Old.get_instance().proteins()


if __name__ == "__main__":
    for protein in mips_proteins():
        print "Protein", protein, "interacts with", 
        print ",".join(set(reduce(list.__add__, [[inter.protein1, inter.protein2] for inter in mips_interactions(protein)], [])) -set([protein]))
            