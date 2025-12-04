from langchain_openai import ChatOpenAI 
import os 
import httpx 
client = httpx.Client(verify=False)
llm = ChatOpenAI(
    base_url="https://genailab.tcs.in",
    model="azure_ai/genailab-maas-DeepSeek-V3-0324",
    api_key="sk-PHXT5d_JGKnDksrzSEI0Xg", # This key is for Hackathon purposes only and should not be used for any unauthorized purposes
    http_client=client
)
print(llm.invoke("Hi"))