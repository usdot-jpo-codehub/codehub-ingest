Codehub-Ingest (Formerly known as Hoard)

Required Pre-Build Configurations
	- In the ingest folder, rename sample-config.yml to config.yml and add the following to it:
	- Github user and access token (required for execution to work without hitting Github rate limits)
	- Amazon SQS queue that this function outputs to

To Build: 
	- docker build -t codehub-ingest .

To Run:
	- docker-compose up

When docker-compose up is run, all repos in all orgs listed in the config file will be cloned and processed by Sonarqube. Results of the scans are then pulled from Sonarqube and written to SQS.