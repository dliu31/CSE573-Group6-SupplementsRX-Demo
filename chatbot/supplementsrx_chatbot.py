import os
import re
import json
import logging
import streamlit as st
from pathlib import Path
from dotenv import load_dotenv
from typing import TypedDict, List, Union
from langgraph.graph import StateGraph, END, START
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.graphs import Neo4jGraph
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_core.messages import HumanMessage, AIMessage
import styling

styling.inject_css()

JSON_DIR = "combined.json"
CHROMA_DIR = "./chroma_db"


load_dotenv()
llm = ChatGoogleGenerativeAI(model='gemini-2.0-flash') # chat model

class AgentState(TypedDict):
    messages: List[Union[HumanMessage, AIMessage]]
    intent: str
    user_query: str
    cypher_query: str
    result: str # this has the kg response
    schema: str
    rag_context: str # this has the rag response
    rag_response: str
    rag_query: str
    web_response: str # this has the web response 
    hist: dict

kg_graph = Neo4jGraph(
    url=os.getenv("NEO4J_URI"),
    username=os.getenv("NEO4J_USERNAME"),
    password=os.getenv("NEO4J_PASSWORD")
)
llm_schema = kg_graph.schema

def cypher_node(state:AgentState) -> AgentState:
    """
    The goal of this agent is to take the user input in natural language and output a cypher query
    """
    # intent = state['intent']
    intent = state['user_query']
    schema = state['schema']
    prompt = ChatPromptTemplate.from_template(
        # Prompting the LLM to return the query within markdown, easier to extract and safer
        "You are a Cypher expert. Convert this intent into a Cypher query. Enclose the query in a markdown code block starting with 'cypher' (e.g., ```cypher\n<query>```).\n\nIntent: {intent}." \
        "Note - Striclty use this graph schema : {schema}. Dont use any terms not inside this schema." 
    )
    chain = prompt | llm
    
    # Get the raw output, which should include markdown
    raw_output = chain.invoke({"intent": intent, "schema": schema}).content
    
    # Use regex to extract the content inside the ```cypher ... ``` block
    match = re.search(r"```[cC]ypher\n(.*?)```", raw_output, re.DOTALL)
    
    if match:
        # If found, use the captured group (the Cypher query)
        cypher_query = match.group(1).strip()
    else:
        # if markdown delimiters aren't used, assume the whole output is the query
        cypher_query = raw_output.strip()
        
    state['cypher_query'] = cypher_query
    return state

def graph_agent(state: AgentState) -> AgentState:
    """The goal of this agent is to execute Cypher query and return results."""
    cypher_query = state["cypher_query"]
    print(f"[Graph Agent] Executing Cypher: {cypher_query}")
    
    # Initialize the key in case of failure
    result_context = "No results or query failed." 
    
    try:
        result = kg_graph.query(cypher_query)
        
        # Format the result into a clean string for the state
        if result is not None and len(result) > 0:
             # This converts the list of records/rows into a single string
            result_context = "\n".join([str(record) for record in result])
        else:
            result_context = "The Cypher query returned no data."

        print(f"[Graph Agent] Query successful. Returning context.")

    except Exception as e:
        # If the query fails (e.g., Cypher syntax error), save the error message
        result_context = f"Cypher query failed with error: {str(e)}"
        print(f"[Graph Agent] Query failed: {e}")

    state['result'] = result_context
    return state

def web_search_agent(state:AgentState) -> AgentState:
    """Search the web for any additional information"""
    search = DuckDuckGoSearchRun(max_results=2)
    query = state['user_query']
    web_result_raw = search.run(query)
    # Clean up and shorten the text
    cleaned = re.sub(r"\s+", " ", web_result_raw).strip()  # collapse whitespace
    sentences = re.split(r"(?<=[.!?])\s+", cleaned)    # split into sentences
    short_summary = " ".join(sentences[:2])
    if len(short_summary) > 500:
        short_summary = short_summary[:500].rsplit(" ", 1)[0] + "..."
    state['web_response'] = short_summary
    return state

def final_node(state:AgentState) -> AgentState:
    query = state["user_query"]
    result = state['result']
    rag_context = state['rag_context']
    web_result = state['web_response']
    ch_hist = state['hist']
    prompt = ChatPromptTemplate.from_template(
        "You are an agent who is an expert on nutritional supplements. "
        "You have been given the following query : {query} and the following result : {result} from the knowledge graph and the follwoing RAG context : {rag_context}"
        "You have also been given the result of a simple web search : {web_result} and the overall chat history : {ch_hist}, which could be empty if it is the first run."
        "chat history is a dict of the form query : output"
        "Give a concise answer that uses the available information as an aswer to the query. Give slightly less importance to the web search result." \
        "Output a string that is the answer, your answer formulation must be as concise and to-the-point as possible." 
    )
    chain = prompt | llm
    resp = chain.invoke({"query": query, "result": result, "rag_context": rag_context, "web_result": web_result, "ch_hist" : ch_hist}).content
    state['result'] = resp
    return state


# RAG code


# load the json file
def load_json(filepath):
    docs = []
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    for item in data:
        text = f"{item['query']}: {item['mechanism_of_action']}"
        meta = {"name": item["query"], "source": filepath}      
        docs.append({"text": text, "meta": meta})
    return docs

def create_chroma_db(docs):
    embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001") # google gemini embeddings model
    splitter = RecursiveCharacterTextSplitter(chunk_size = 600, chunk_overlap=100)
    doc_texts = []
    doc_metas = []
    for i in docs:
        for chunk in splitter.split_text(i["text"]):
            doc_texts.append(chunk) # get all the text data chunks
            doc_metas.append(i['meta']) # get all the metadata chunks
    if not os.path.exists(CHROMA_DIR):
        db = Chroma.from_texts(
            texts = doc_texts,
            embedding=embeddings,
            metadatas=doc_metas,
            persist_directory=CHROMA_DIR
        )
        db.persist()
        print(f"Finished creating vector store")
    else:
        print(f"Vector store  already exists. No need to initialize.")
    return db

# define the nodes for the retrieval
# this retrival is piped into the final node above

def retrieve(state: AgentState):
    """Retrieve the top 5 relevant docs fron the chroma db"""
    query = state['rag_query']
    embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
    db = Chroma(persist_directory=CHROMA_DIR, embedding_function=embeddings)
    retriever = db.as_retriever(search_type="similarity", search_kwargs={"k":5})
    docs = retriever.invoke(query)
    state['rag_context'] = "\n\n".join([d.page_content for d in docs])

    return state


docs = load_json(JSON_DIR)
if not docs:
    print("No docs found in json_docs/")
    exit()

if not Path(CHROMA_DIR).exists():
    create_chroma_db(docs)
    print(f"Ingested {len(docs)} docs into Chroma")
else:
    print("Using existing ChromaDB")






    
# graph
workflow = StateGraph(AgentState)
workflow.add_node("cypher_agent", cypher_node)
workflow.add_node("graph_agent", graph_agent)
workflow.add_node("final_node", final_node)
workflow.add_node("retrieve_node", retrieve)
workflow.add_node("web_node", web_search_agent)


workflow.add_edge("cypher_agent", "graph_agent")
workflow.add_edge("graph_agent", "retrieve_node")
workflow.add_edge("retrieve_node", "web_node")
workflow.add_edge("web_node", "final_node")
workflow.add_edge("final_node", END)

workflow.set_entry_point("cypher_agent")

app = workflow.compile()


# Integration with streamlit and converstional loop

# page config
st.set_page_config(page_title="Langgraph Agent", layout="centered")




prompt_template = ChatPromptTemplate.from_messages([
    ("system",
     "You are an assistant that summarizes the user's underlying goal or intent "
     "based on the conversation. Respond with one clear, natural-language sentence "
     "that captures what the user is trying to do. Keep the following chat history in mind {overall_history}, which is a dictionary of the form (user query: result) and use it if needed"),
    ("human", "{conversation}")
])


# Streamlit session state


st.title("Supplements AI 💊")
st.caption("Not medical advice. Talk to a licensed professional before starting any supplement.")

if "summary" not in st.session_state:
    st.session_state.summary = True
    st.markdown("Welcome to the SupplementsRX Chatbot")
   
    styling.render_message(
        role='assistant',
        pretty_role='Supplements AI',
        content="I am a helpful assistant that you can use to find information on a variety of supplements. Type your query below to get started!"
    )

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "intent" not in st.session_state:
    st.session_state.intent = None
if "refining" not in st.session_state:
    st.session_state.refining = True  # start in refinement mode
if "chat_hist" not in st.session_state:
    st.session_state.chat_hist = {}

logging.basicConfig(
    filename="app_log.txt",          # Log file name
    level=logging.INFO,              # Log level
    format="%(asctime)s - %(message)s",
    filemode="a"                     # Append mode (don’t overwrite file)
)


# function to refine intent
def intent_refinement(messages, hist):
    conv_hist = "\n".join(
        [f"User: {m.content}" if isinstance(m, HumanMessage)
         else f"Assistant: {m.content}" for m in messages]
    )
    prompt = prompt_template.format_messages(conversation=conv_hist, overall_history = hist)
    response = llm.invoke(prompt)
    return response.content.strip()


# display chat history in UI

for msg in st.session_state["messages"]:
    if isinstance(msg, HumanMessage):
        role = "user"
    else:
        role = "assistant"
    # normalize roles so we only have "user" or "assistant"
    normalized_role = "user" if role == "user" else "assistant"
    pretty_role = "You" if normalized_role == "user" else "Supplements AI"
    content = msg.content
    #render each message with custom styling as defined in styling.py
    styling.render_message(
        role=normalized_role,
        pretty_role=pretty_role,
        content=msg.content
    )



# if the intent is being refined, show approve and reject boxes below the message that the ai retuns
accept_clicked = False
if st.session_state.intent:
        accept_clicked = st.button("Accept", key="accept_btn")


if not st.session_state.intent:
    user_input = st.chat_input("How May I Help You?")
else:
    user_input = st.chat_input("Please refine your intent or press Accept to proceed.")

user_action = user_input or accept_clicked
# chat_hist = {}
if user_action:
    if user_input:
        st.session_state.messages.append(HumanMessage(content=user_input))
    # Detect approval or run command
    if accept_clicked:
        if st.session_state.intent:
            st.session_state.refining = False
            # st.session_state.messages.append(
            #     AIMessage(content=f"Approved intent:\n\n> {st.session_state.intent}\n\nRunning LangGraph...")
            # )
            with st.spinner("Thinking..."):
                state = AgentState(user_query=st.session_state.intent, schema=llm_schema, rag_query=st.session_state.intent, hist=st.session_state.chat_hist)
                result = app.invoke(state)
                output = result.get("result", "No result.")
                st.session_state.messages.append(AIMessage(content=f"System Output:\n\n{output}"))
                st.session_state.chat_hist[st.session_state.intent] = output
                if len(st.session_state.chat_hist) > 2:
                    oldest = list(st.session_state.chat_hist.keys())[0]
                    del st.session_state.chat_hist[oldest]
                # logging.info(f"conversation history:\n\n\n{st.session_state.chat_hist}") # log the conversation history into a text file
                # print("HISTORY: ", st.session_state.chat_hist)
                with open("log.txt", "a") as f:
                    f.write(f"{st.session_state.intent} : {output}\n\n")

                # Reset for next query
                st.session_state.refining = True
                st.session_state.intent = None
                # st.session_state.messages.append(
                #     AIMessage(content="You can now ask another question")
                # )
        
        else:
            st.session_state.messages.append(AIMessage(content="No intent to approve yet. Please refine first."))
        st.rerun()

    elif st.session_state.refining: # if intent is still being refined
        # Refine intent
        with st.spinner("Thinking..."):
            refined = intent_refinement(st.session_state.messages, st.session_state.chat_hist) #########################
            st.session_state.intent = refined
            response = (
                f"Here's my current understanding of your intent:\n\n> {refined}"
                "\n\nSelect 'Accept' to confirm, or keep chatting to refine further."
            )
        st.session_state.messages.append(AIMessage(content=response))
        st.rerun()



