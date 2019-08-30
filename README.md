# Codehub-Ingest (Formerly known as Hoard)

## Required Pre-Build Configurations
In the ingest folder, rename sample-config.yml to config.yml and add the following to it:
1. Github user and access token (required for execution to work without hitting Github rate limits)
2. Amazon SQS queue that this function outputs to

## Build
`docker build -t codehub-ingest .`

## Execution
`docker-compose up`

When `docker-compose up` is run, all repos in all orgs listed in the config file will be cloned and processed by Sonarqube. Results of the scans are then pulled from Sonarqube and written to SQS.
