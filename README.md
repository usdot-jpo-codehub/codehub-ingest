# Codehub-Ingest (Formerly known as Hoard) ![Build Status](https://codebuild.us-east-1.amazonaws.com/badges?uuid=eyJlbmNyeXB0ZWREYXRhIjoiRlVBSTZReThlVEpqcDNJMFg2NnBoYTU3VkxEZktpSFpDd1NnZ3Y3LzBlbnYyRHZSTW1DNDNOa0I5bWVJK1ZFQ1MvVTNLQk1jSXZNbHBwcTlEYTQ1Q0V3PSIsIml2UGFyYW1ldGVyU3BlYyI6IkdKdUdIMllGeXoyUjIzNjciLCJtYXRlcmlhbFNldFNlcmlhbCI6MX0%3D&branch=master)

## Required Pre-Build Configurations
The following environment variables need to be configured:
1. `GITHUB_USER` 
2. `GITHUB_ACCESS_TOKEN` (required for execution to work without hitting Github rate limits)
3. `ELASTICSEARCH_API_BASE_URL` (eg: http://localhost:9200)


## Execution
When execution occurs, all individual repos and all repos owned by orgs listed in the config file will be cloned and processed by Sonarqube and Clamscan. Results of the scans are then processed and written to Elasticsearch.

