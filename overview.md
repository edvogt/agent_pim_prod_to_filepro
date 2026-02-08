# agent_pimcore_pull_from_filepro - Component Overview

Component,Responsibility,Key Functionality
Pimcore Client,Fetching & Asset Retrieval,"GraphQL queries to Pimcore, product filtering by PartPrefix, asset/image retrieval"
Fetch Engine,Product Display & Output,"Main product fetching loop, progress tracking, product information display (verbose/compact modes)"
Pydantic Models,Data Cleaning & Logic,"Data validation, HTML sanitization, price calculation, title generation"
