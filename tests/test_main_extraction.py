import os
import json
import sys
import importlib.util

def import_module_from_file(module_name, file_path):
    """Import a module from a file path"""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module

def test_extraction_method():
    """Test the extraction method in main.py"""
    # Find the main.py file
    main_file = "main.py"
    if not os.path.exists(main_file):
        main_file = "sejusaas/main.py"
        if not os.path.exists(main_file):
            print(f"Could not find main.py file")
            return False
    
    print(f"Using main.py file at {main_file}")
    
    # Import the module
    try:
        main_module = import_module_from_file("main", main_file)
        print("Successfully imported main.py")
    except Exception as e:
        print(f"Error importing main.py: {str(e)}")
        return False
    
    # Check if the extraction method exists
    analyzer_class = getattr(main_module, "COH3StatsAnalyzer", None)
    if not analyzer_class:
        print("Could not find COH3StatsAnalyzer class in main.py")
        return False
    
    # Check if the extraction method exists
    if not hasattr(analyzer_class, "extract_match_data_from_table"):
        print("Could not find extract_match_data_from_table method in COH3StatsAnalyzer class")
        return False
    
    if not hasattr(analyzer_class, "get_real_matches_from_html"):
        print("Could not find get_real_matches_from_html method in COH3StatsAnalyzer class")
        return False
    
    print("Found extraction methods in main.py")
    
    # Create a mock analyzer instance
    try:
        # Create a subclass that overrides the __init__ method
        class MockAnalyzer(analyzer_class):
            def __init__(self):
                # Skip the original __init__ method
                pass
        
        analyzer = MockAnalyzer()
        print("Created mock analyzer instance")
    except Exception as e:
        print(f"Error creating mock analyzer instance: {str(e)}")
        return False
    
    # Test the extraction method
    try:
        # Find the HTML file
        html_file = "sejusaas/player_page_playwright_seju-fuminguez.html"
        if not os.path.exists(html_file):
            html_file = "player_page_playwright_seju-fuminguez.html"
            if not os.path.exists(html_file):
                print(f"Could not find HTML file")
                return False
        
        print(f"Using HTML file at {html_file}")
        
        # Call the extraction method
        matches = analyzer.extract_match_data_from_table(html_file, "73550", "seju-fuminguez")
        
        if not matches:
            print("No matches found")
            return False
        
        print(f"Found {len(matches)} matches")
        
        # Print the first 3 matches
        print("\nFirst 3 matches:")
        for i, match in enumerate(matches[:3]):
            print(f"Match {i+1}:")
            print(f"  Date: {match['match_date']}")
            print(f"  Result: {match['match_result']} ({match['rating_change']})")
            print(f"  Map: {match['map_name']}")
            print(f"  Mode: {match['match_type']} ({match['duration']})")
            print(f"  Axis Players: {len(match['axis_players'])}")
            print(f"  Allies Players: {len(match['allies_players'])}")
            print()
        
        # Save the matches to a JSON file
        output_file = "test_main_extraction_matches.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(matches, f, indent=2)
        
        print(f"Saved {len(matches)} matches to {output_file}")
        
        return True
    except Exception as e:
        print(f"Error testing extraction method: {str(e)}")
        return False

def main():
    print("Testing extraction method in main.py...")
    if test_extraction_method():
        print("Test completed successfully!")
    else:
        print("Test failed.")

if __name__ == "__main__":
    main() 