import pandas as pd
import spacy
from rdflib import Graph, URIRef, Literal, Namespace
from rdflib.namespace import RDF, RDFS
import os

# ==========================================
# SETUP INSTRUCTIONS:
# 1. pip install pandas rdflib spacy scispacy
# 2. Install the medical model:
#    pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.4/en_core_sci_sm-0.5.4.tar.gz
# ==========================================

def load_ner_model():
    """Loads the medical NER model and attaches the UMLS Entity Linker."""
    try:
        print("Loading Medical NER model (en_core_sci_sm)...")
        nlp = spacy.load("en_core_sci_sm")
        
        # --- NEW: ADDING UMLS LINKER ---
        # The linker maps extracted entities to the Unified Medical Language System (UMLS)
        try:
            # We import EntityLinker to register it with spaCy's architecture
            from scispacy.linking import EntityLinker
            print("Adding UMLS Entity Linker...")
            print("(Note: On first run, this will download the UMLS vocabulary cache which is quite large)")
            
            # Add the linker to the pipeline
            nlp.add_pipe("scispacy_linker", config={"resolve_abbreviations": True, "linker_name": "umls"})
        except ImportError:
            print("WARNING: scispacy linking module not found. Skipping UMLS Entity Linker.")
            print("To enable CUIs, ensure scispacy is installed: pip install scispacy")
            
    except OSError:
        # Fallback logic
        print("WARNING: Medical model 'en_core_sci_sm' not found.")
        print("Please run: pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.4/en_core_sci_sm-0.5.4.tar.gz")
        print("Falling back to standard english model...")
        try:
            nlp = spacy.load("en_core_web_sm")
        except OSError:
            spacy.cli.download("en_core_web_sm")
            nlp = spacy.load("en_core_web_sm")
            
    return nlp

def extract_medical_entities(nlp, text):
    """
    Extracts entities and their UMLS CUI (Concept Unique Identifier).
    Returns a dictionary: { "CUI_ID": "Entity Name" }
    """
    if pd.isna(text):
        return {}
    
    doc = nlp(text)
    extracted = {}
    
    # Check if the linker was successfully added to the pipeline
    has_linker = "scispacy_linker" in nlp.pipe_names
    
    for ent in doc.ents:
        entity_name = ent.text.lower().strip()
        
        # --- NEW: GETTING THE CUI ---
        cui_id = None
        if has_linker and ent._.kb_ents:
            # ent._.kb_ents contains a list of (cui, score) matches. We take the highest scoring one.
            best_match_cui, score = ent._.kb_ents[0]
            
            # Only use the CUI if the model is highly confident (e.g., > 75% match)
            if score > 0.75:
                cui_id = best_match_cui
                
        # If we found a CUI, use it as the unique key. Otherwise, fallback to the string.
        unique_key = cui_id if cui_id else entity_name.replace(" ", "_").replace(",", "")
        
        # By using a dictionary, we deduplicate by CUI automatically! 
        # For example, if "dyspnea" and "shortness of breath" both resolve to C0013404,
        # they will safely overwrite the same key and only create ONE node.
        extracted[unique_key] = entity_name
        
    return extracted

def process_csv_to_rdf(csv_path, output_path="disease_graph.ttl"):
    # 1. Initialize NER Model with UMLS Linker
    nlp = load_ner_model()
    
    print(f"\nLoading data from {csv_path}...")
    df = pd.read_csv(csv_path)
    
    # 3. Apply Medical NER & UMLS Linking
    print("Applying Medical NER & UMLS Linking... (This might take some time)")
    df['extracted_symptoms'] = df['common_symptom'].apply(lambda text: extract_medical_entities(nlp, text))
    
    # Show preview
    print("\nExtraction Preview (first 2 rows):")
    for _, row in df.head(2).iterrows():
        print(f"Disease: {row['disease']}")
        print(f"  Raw: {row['common_symptom']}")
        print(f"  CUIs Found: {row['extracted_symptoms']}\n")

    # 4. Set up RDFLib Graph
    print("Building Semantic RDF Graph using CUIs...")
    g = Graph()
    
    MED = Namespace("http://example.org/medical/")
    DISEASE = Namespace("http://example.org/medical/disease/")
    
    # --- NEW: Add standard namespace for UMLS IDs ---
    UMLS = Namespace("http://linkedlifedata.com/resource/umls/id/")
    
    g.bind("med", MED)
    g.bind("disease", DISEASE)
    g.bind("umls", UMLS)
    
    for index, row in df.iterrows():
        disease_name = str(row['disease']).strip()
        symptoms_dict = row['extracted_symptoms']
        
        disease_uri_str = disease_name.replace(" ", "_").replace(",", "").lower()
        disease_node = DISEASE[disease_uri_str]
        
        g.add((disease_node, RDF.type, MED.Disease))
        g.add((disease_node, RDFS.label, Literal(disease_name)))
        
        # Add relationships using CUIs
        for unique_id, symp_name in symptoms_dict.items():
            
            # --- NEW: Map to UMLS Namespace if it is a CUI ---
            if unique_id.startswith("C") and unique_id[1:].isdigit(): 
                # It's a UMLS CUI (e.g. C0013404)
                symp_node = UMLS[unique_id]
            else:
                # Fallback if no CUI was confident enough
                symp_node = MED[f"symptom/{unique_id}"]
            
            g.add((symp_node, RDF.type, MED.Symptom))
            g.add((symp_node, RDFS.label, Literal(symp_name.title())))
            g.add((disease_node, MED.has_symptom, symp_node))

    print(f"\nSaving RDF graph to {output_path}...")
    g.serialize(destination=output_path, format="turtle")
    print(f"Success! Graph generated with {len(g)} triples.")

if __name__ == "__main__":
    csv_file = "disease_data.csv"
    if os.path.exists(csv_file):
        process_csv_to_rdf(csv_file)
    else:
        print(f"Error: {csv_file} not found in the current directory.")
