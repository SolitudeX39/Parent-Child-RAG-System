import os
import json
import requests
from dotenv import load_dotenv
from openrouter_rerank import OpenRouterRerank 

load_dotenv()
# Fetch the key from your .env file
MY_API_KEY = os.getenv("OPENROUTER_API_KEY")

def run_openrouter_style_test():
    # Defensive check to ensure your .env loaded properly
    if not MY_API_KEY:
        print("Error: OPENROUTER_API_KEY not found in environment variables.")
        return

    response = requests.post(
        url="https://openrouter.ai/api/v1/rerank",
        headers={
            # FIXED: Dynamically injects your API key variable using an f-string
            "Authorization": f"Bearer {MY_API_KEY}",
            "Content-Type": "application/json",
            # OPTIONAL: Replace these or remove them if not deploying a live web app
            "HTTP-Referer": "http://localhost:3000", 
            "X-OpenRouter-Title": "Local Test Script", 
        },
        data=json.dumps({
            "model": "nvidia/llama-nemotron-rerank-vl-1b-v2:free",
            "query": "what is an ai agent?",
            "documents": [
                {'text': 'Agent design \nfoundationsIn its most fundamental form, an agent consists of three core components:\n01 Model The LLM powering the agent’s reasoning and decision-making\n02 T ools External functions or APIs the agent can use to take action\n03 Instructions Explicit guidelines and guardrails defining how the \u2028\nagent behaves\nHere’s what this looks like in code when using OpenAI’s Agents SDK. Y ou can also implement the \nsame concepts using your preferred library or building directly from scratch.\nPython\n1\n2\n3\n4\n5\n6\nweather_agent = Agent(\n\xa0\xa0\xa0name=\ninstructions=\n\xa0\xa0\xa0\xa0tools=[get_weather],\n)\n\xa0 ,\n "Weather agent"\n"You are a helpful agent who can talk to users about the \nweather.",\n7 A practical guide to building agents'},
                {'text': "What is an \nagent?\nWhile conventional software enables users to streamline and automate workflows, agents are able \nto perform the same workflows on the users’ behalf with a high degree of independence.\nAgents are systems that independently accomplish tasks on your behalf.\nA workflow is a sequence of steps that must be executed to meet the user’s goal, whether that's \nresolving a customer service issue, booking a restaurant reservation, committing a code change, \u2028\nor generating a report.\nApplications that integrate LLMs but don’t use them to control workflow execution—think simple \nchatbots, single-turn LLMs, or sentiment classifiers—are not agents.\nMore concretely, an agent possesses core characteristics that allow it to act reliably and \nconsistently on behalf of a user:\n01 It leverages an LLM to manage workflow execution and make decisions. It recognizes \nwhen a workflow is complete and can proactively correct its actions if needed. In case \u2028\nof failure, it can halt execution and transfer control back to the user.\n02 It has access to various tools to interact with external systems—both to gather context \nand to take actions—and dynamically selects the appropriate tools depending on the \nworkflow’s current state, always operating within clearly defined guardrails.\n4 A practical guide to building agents"},
                {'text': '24\n25\n26\n27\n28\n29\n30\n32\n32\n33\n)\n\n  main():\n\xa0\xa0\xa0\xa0msg = input( )\n\n\xa0\xa0\xa0\xa0orchestrator_output = await Runner.run(\n\xa0\xa0\xa0\xa0\xa0\xa0\xa0\xa0manager_agent,msg)\n\n\xa0\xa0\xa0\xa0  message  orchestrator_output.new_messages:\n\xa0\xa0\xa0\xa0\xa0\xa0\xa0\xa0 (f"\xa0 -  {message.content}")\nasync def\nfor in\nprint\n"Translate \'hello\' to Spanish, French and Italian for me!"\nTranslation step:\nDeclarative vs non-declarative graphs\u2028\u2028\nSome frameworks are declarative, requiring developers to explicitly define every branch, loop, \nand conditional in the workflow upfront through graphs consisting of nodes (agents) and \nedges (deterministic or dynamic handoffs). While beneficial for visual clarity, this approach \ncan quickly become cumbersome and challenging as workflows grow more dynamic and \ncomplex, often necessitating the learning of specialized domain-specific languages.\nIn contrast, the Agents SDK adopts a more flexible, code-first approach. Developers can \u2028\ndirectly express workflow logic using familiar programming constructs without needing to \u2028\npre-define the entire graph upfront, enabling more dynamic and adaptable agent orchestration.\n20 A practical guide to building agents'}   
                ],
            "top_n": 3
        })
    )

    # Debugging check to catch API errors gracefully before parsing
    if response.status_code != 200:
        print(f"API Error ({response.status_code}): {response.text}")
        return

    results = response.json()
    
    # Safely navigate the dictionary
    for result in results.get("results", []):
        document = result["document"]
        source = document.get("text") 
        print(f"Index: {result['index']}, Score: {result['relevance_score']}, Source: {source}")

if __name__ == "__main__":
    run_openrouter_style_test()
