import re
import yaml
from pathlib import Path
from difflib import SequenceMatcher

def load_metrics():
    # Construct path to data/metrics.yaml
    yaml_path = Path(__file__).parent.parent.parent / "data" / "metrics.yaml"
    # Ensure directory exists in case it doesn't
    yaml_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(yaml_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

# Load metrics on module import
METRICS = load_metrics()

def fuzzy_contains(query: str, alias: str, threshold=0.85) -> bool:
    """
    Slides a window over the query words to find a fuzzy match for the alias.
    Naturally handles typos and plurals without strict regex boundaries.
    """
    query_words = re.sub(r'[^\w\s]', '', query.lower()).split()
    alias_words = alias.lower().split()
    alias_len = len(alias_words)
    
    if alias_len == 0 or alias_len > len(query_words): 
        return False
        
    for i in range(len(query_words) - alias_len + 1):
        window = " ".join(query_words[i:i+alias_len])
        score = SequenceMatcher(None, window, alias.lower()).ratio()
        if score >= threshold:
            return True
    return False

def inject_business_rules(user_query: str) -> str:
    """
    Scans the user query for metric aliases and appends strict business definitions
    to the prompt if found. Uses fuzzy matching to gracefully handle user typos.
    """
    injected_rules = []
    
    # Check for broad intent
    broad_keywords = ["metric", "metrics", "kpi", "kpis", "summary", "overview", "stats", "statistics"]
    is_broad = any(re.search(rf"\b{kw}\b", user_query, re.IGNORECASE) for kw in broad_keywords)
    
    for metric_name, data in METRICS.items():
        aliases = data.get("aliases", [])
        rule_text = data.get("rule", "")
        
        if is_broad:
            injected_rules.append(f"- {metric_name}: {rule_text}")
            continue
            
        # Iterate over aliases and try to find a match
        for alias in aliases:
            if fuzzy_contains(user_query, alias):
                injected_rules.append(f"- {metric_name}: {rule_text}")
                # Break on first match for this metric to avoid injecting the same rule twice
                break 

    if not injected_rules:
        return user_query
        
    # Append the rules to the end of the user query
    rules_context = "\n\nBusiness Rules to strictly follow:\n" + "\n".join(injected_rules)
    return user_query + rules_context

if __name__ == "__main__":
    queries = [
        "What is our aov?",
        "Who are the most active customers this month?",
        "Show me gross revenues by country"
    ]
    
    for q in queries:
        print(f"Original: {q}")
        print(f"Injected:\n{inject_business_rules(q)}")
        print("-" * 50)
