from neo4j import GraphDatabase

# ==========================================
# SETUP INSTRUCTIONS:
# pip install neo4j
# ==========================================

def test_connection_and_query(uri, user, password):
    print(f"Attempting to connect to Neo4j Aura at: {uri}\n")
    
    try:
        # 1. Establish the driver connection
        driver = GraphDatabase.driver(uri, auth=(user, password))
        
        # 2. Verify connectivity (this will throw an error if password/URI is wrong)
        driver.verify_connectivity()
        print("✅ SUCCESS: Successfully authenticated and connected to Neo4j Aura!\n")
        
        # 3. Run a test query to pull data
        print("Running a test Cypher query to check for your medical data...")
        
        with driver.session() as session:
            # Query 1: Count total nodes to prove data exists
            count_result = session.run("MATCH (n) RETURN count(n) AS total_nodes")
            total_nodes = count_result.single()["total_nodes"]
            print(f"📊 Graph Size: Found {total_nodes} total nodes in the database.")
            
            if total_nodes == 0:
                print("⚠️  Warning: The database is connected, but it is empty.")
                print("Make sure you ran the upload_ttl_to_aura.py script successfully.")
            else:
                # Query 2: Fetch 3 actual relationships to prove the RDF format worked
                print("\n🔍 Fetching 3 sample Disease-Symptom relationships:")
                query = """
                MATCH (d)-[r:has_symptom]->(s)
                RETURN d.label AS Disease, s.label AS Symptom
                LIMIT 3
                """
                sample_result = session.run(query)
                
                for record in sample_result:
                    print(f"   - [Disease: {record['Disease']}] -> HAS_SYMPTOM -> [Symptom: {record['Symptom']}]")
                    
        print("\n✅ Test Complete!")
                    
    except Exception as e:
        print(f"❌ ERROR: Failed to connect or query the database.")
        print(f"Details: {e}")
    finally:
        # Always clean up the connection
        if 'driver' in locals():
            driver.close()

if __name__ == "__main__":
    AURA_URI = "neo4j+s://9477a102.databases.neo4j.io"
    AURA_USERNAME = "9477a102"
    AURA_PASSWORD = "Am6H5wH0IMLBkBe30lN9Rf365Tf9vqQvPUJmj1uUWtI"
    
    test_connection_and_query(AURA_URI, AURA_USERNAME, AURA_PASSWORD)
