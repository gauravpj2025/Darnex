import pickle
import os

graph_file = os.path.join('models', 'railway_graph.gpickle')

print(f"Checking existence: {os.path.exists(graph_file)}")

try:
    with open(graph_file, 'rb') as f:
        graph = pickle.load(f)
    print(f"Loaded graph with {len(graph.nodes())} nodes.")
    print(f"Nodes: {list(graph.nodes())}")
except Exception as e:
    print(f"Failed to load railway graph: {e}")
