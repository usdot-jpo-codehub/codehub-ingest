import yaml
import requests
import json
import os
from os.path import expanduser
from subprocess import call,check_output,Popen,PIPE
import subprocess
import json,pickle
import shutil 
import glob2
import boto3
from datetime import datetime
import base64
import time
import hashlib


with open("config.yml", 'r') as stream:
    config = yaml.load(stream, Loader=yaml.FullLoader)


def getReposToIngest(repo = "all"):
    reposToIngest = []
    if repo == "all" :
        repo_list_resp = requests.get(os.environ['ELASTICSEARCH_API_BASE_URL'] + '/repositories/_search?size=10000')
        repo_list_json = json.loads(repo_list_resp.text)['hits']['hits']
        for repoESObj in repo_list_json:
            if repoESObj['_source']['codehubData']['isIngestionEnabled'] == True:
                reposToIngest.append(repoESObj)

    return reposToIngest

def ingestRepos(repoESObjs):
    result = []
    for repoESObj in repoESObjs:
        repo = repoESObj['_source']
        repo_name = repo['sourceData']['owner']['name'] + '/' + repo['sourceData']['name']
        repo_etag = repo['codehubData']['etag']

        ghresponse = requests.get('https://api.github.com/repos/' + repo_name + '?access_token='+os.environ['GITHUB_ACCESS_TOKEN'], headers={'If-None-Match': repo_etag})

        # gh_rate_limit_remaining = 5000 # Default quota for Github.
        gh_rate_limit_remaining = ghresponse.headers['X-RateLimit-Remaining']
        if (ghresponse.headers['Status'] != '304 Not Modified'):
            if (ghresponse.headers['Status'] == '200 OK'):
                
                print("Adding " + repo_name + " to batch and updating etag")
                repo['codehubData']['etag'] = ghresponse.headers['ETag']
                
                repo = mapRepoData(repo, ghresponse.text)
                repo = getGeneratedData(repo)
                repo = updateCodehubData(repo)

                repoESObj['_source'] = repo
                result.append(repoESObj)

            else:
                print("Error ingesting " + repo_name + ". ==> Skipping.")
                print("Error: " + ghresponse.headers['Status'] + ' ==> ' + ghresponse.text)

                sendSlackNotification('Error ingesting ' + repo_name)
        else:
            print("Repo " + repo_name + " already up to date. Skipping...")

    sendSlackNotification("Ingest complete. " + str(gh_rate_limit_remaining) + " api calls remaining until reset")
    return result

def writeToElasticSearch(repoESObjs):
    payload = ""
    for repoESObj in repoESObjs:
        payload += '{"index": {"_index": "repositories", "_id": "' + repoESObj['_id'] + '"}}\r\n'
        payload += json.dumps(repoESObj['_source']) + '\r\n'

    if(payload != ''):
        print('Writing data to ElasticSearch')
        header = {'Content-type': 'application/json'}
        es_post_response = requests.post(os.environ['ELASTICSEARCH_API_BASE_URL'] + '/_bulk', data=payload, headers=header)
        print('Data written to ElasticSearch')
        print(es_post_response.text)

    else:
        print('ElasticSearch already up to date.')


def mapRepoData(repo, githubData):
    ghDataObj = json.loads(githubData)

    repo['sourceData']['name'] = ghDataObj['name']
    repo['sourceData']['repositoryUrl'] = ghDataObj['html_url']
    repo['sourceData']['language'] = ghDataObj['language']
    repo['sourceData']['languages'] = json.loads(get_github_property(repo, 'languages'))
    repo['sourceData']['description'] = ghDataObj['description']
    repo['sourceData']['createdAt'] = ghDataObj['created_at']
    repo['sourceData']['lastPush'] = ghDataObj['pushed_at']
    repo['sourceData']['stars'] = ghDataObj['stargazers_count']
    repo['sourceData']['watchers'] = ghDataObj['watchers_count']
    repo['sourceData']['defaultBranch'] = ghDataObj['default_branch']

    repo['sourceData']['owner'] = getGithubOwnerObject(ghDataObj)

    contributionMap = getRepoContributions(json.loads(get_github_property(repo, 'contributors')))
    repo['sourceData']['commits'] = contributionMap['commitTotal']
    repo['sourceData']['contributors'] = contributionMap['contributorsMap']

    repo['sourceData']['forks'] = getForks(json.loads(get_github_property(repo, 'forks')))

    repo['sourceData']['readme'] = getGithubReadmeObject(json.loads(get_github_property(repo, 'readme')))

    repo['sourceData']['releases'] = getReleases(json.loads(get_github_property(repo, 'releases')))

    return repo  
    
def getGeneratedData(repo):
    cloneGithubRepo(repo)
    runSonarScan(repo)

    # Waiting 5 sec to allow sonar to process results before querying
    time.sleep(5)

    # retrieve Sonar results
    repo['generatedData']['sonarMetrics'] = get_sonar_metrics(repo)
    # run virus scan
    repo['generatedData']['vscan'] = runVirusScan(repo)

    repo['generatedData']['rank'] = calculateRank(repo)

    return repo

def updateCodehubData(repo):
    current_time = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    repo['codehubData']['lastIngested'] = current_time

    if (repo['codehubData']['isIngested'] == False):
        repo['codehubData']['isIngested'] = True
        repo['codehubData']['isVisible'] = True
    return repo



def get_github_property(repo, property_name):
    owner = repo['sourceData']['owner']['name']
    name = repo['sourceData']['name']
    return requests.get('https://api.github.com/repos/' + owner + '/' + name + '/' + property_name + '?access_token='+os.environ['GITHUB_ACCESS_TOKEN']).text

def getGithubOwnerObject(repo):
    owner = {}
    owner['name'] = repo['owner']['login']
    owner['url'] = repo['owner']['url']
    owner['avatarUrl'] = repo['owner']['avatar_url']
    owner['type'] = repo['owner']['type']
    return owner

def getRepoContributions(contributorsJson):
    commitTotal = 0
    contributors = []
    for contributorJson in contributorsJson:
        commitTotal += contributorJson['contributions']
        contributor = {}
        contributor['userType'] = contributorJson['type']
        if(contributorJson['type']=='User'):
            contributor['username'] = contributorJson['login']
            contributor['profileUrl'] = contributorJson['html_url']
            contributor['avatarUrl'] = contributorJson['avatar_url']
        else:
            contributor['username'] = ''
            contributor['profileUrl'] = ''
            contributor['avatarUrl'] = ''
        contributors.append(contributor)
    contributionMap = {'commitTotal': commitTotal, 'contributorsMap': contributors}
    return contributionMap

def getForks(forksJson):
    result = []
    for fork in forksJson:
        repo = {}
        repo['id'] = str(fork['owner']['id']) + '-' + str(fork['id'])
        repo['name'] = str(fork['name'])
        repo['owner'] = str(fork['owner']['login'])
        result.append(repo)
    return result

def getGithubReadmeObject(readmeObj):
    result = {}
    if 'content' in readmeObj:
        decoded_readme = str(base64.b64decode(readmeObj['content']),'utf-8')
        result['content'] = decoded_readme
        result['url'] = readmeObj['url']
    else:
        result = {'content': '', 'url': ''}

    return result

def getReleases(releasesJson):
    results = []
    for release in releasesJson:
        result = {}
        result['tagName'] = release['tag_name']
        result['name'] = release['name']
        result['id'] = release['id']
        # none of the test cases currently have assets or download counts. Will test this later
        result['assets'] = []
        result['downloads'] = 0
        results.append(result)
    return results

def calculateRank(repo):
    result = (repo['sourceData']['stars']*3) + (repo['sourceData']['watchers']*4) + (len(repo['sourceData']['contributors'])*5) + repo['sourceData']['commits']
    return result

def cloneGithubRepo(repo):
    ownerName = repo['sourceData']['owner']['name']
    repoName = repo['sourceData']['name']

    rootdir = expanduser("~") + '/cloned_projects'
    repodir = rootdir + '/' + ownerName + '/' + repoName

    if os.path.exists(repodir):
        os.chdir(repodir)
    else:
        os.makedirs(repodir)
        os.chdir(repodir)

    clone_url = 'https://' + os.environ['GITHUB_USER'] + ':' + os.environ['GITHUB_ACCESS_TOKEN']+'@github.com/' + ownerName + '/' + repoName + '.git'
    call(["git","clone",clone_url])


def runSonarScan(repo):
    ownerName = repo['sourceData']['owner']['name']
    repoName = repo['sourceData']['name']

    cloned_project_path = expanduser("~") + '/cloned_projects/' + ownerName + '/' + repoName

    exclusions = '**/system/**, **/test/**, **/img/**, **/logs/**, **/fonts/**, **/generated-sources/**, **/packages/**, **/docs/**, **/node_modules/**, **/bower_components/**,**/dist/**,**/unity.js,**/bootstrap.css, **/tools/**'

    file_object = open(cloned_project_path + "/sonar-project.properties", 'w')

    file_object.write("sonar.projectKey=" + ownerName + ":" + repoName)
    file_object.write("\n")
    file_object.write("sonar.projectName="+repoName+" of "+ownerName)
    file_object.write("\n")
    file_object.write("sonar.projectVersion=1.0")
    file_object.write("\n")
    file_object.write("sonar.sources="+cloned_project_path)
    file_object.write("\n")
    file_object.write("sonar.exclusions=file:"+exclusions)
    file_object.write("\n")
    file_object.write("sonar.sourceEncoding=UTF-8")
    file_object.close()
    
    curr_dir = os.getcwd()
    os.chdir(cloned_project_path)
    call('pwd')
    call(config['sonar_runner_path'], shell=True)
    os.chdir(curr_dir)

def get_sonar_metrics(repo):
    ownerName = repo['sourceData']['owner']['name']
    repoName = repo['sourceData']['name']

    metrics_list = config['sonar_health_metrics']
    health_metrics_map = {}

    res = '_response'
    for metric in metrics_list:
        returned_res = requests.get(os.environ['SONAR_API_BASE_URL']+'/api/resources?resource='+ownerName+':'+repoName+'&metrics='+metric, auth=('admin', 'admin'))
        returned_json = {}
        if(returned_res.status_code == 200):
            if(len(json.loads(returned_res.text)) > 0):
                if 'msr' in json.loads(returned_res.text)[0]:
                    returned_json = json.loads(returned_res.text)[0]['msr']
                    if len(returned_json) > 0:                        
                        health_metrics_map[metric] = returned_json[0]
                    else:
                        health_metrics_map[metric] = {}
            else:
                print ('Health metrics not found for ' + ownerName +'/'+repoName)
                health_metrics_map[metric] = {}
    metrics_result = {}
    for metric in health_metrics_map:
        if 'key' in health_metrics_map[metric]:
            metric_obj = {}
            metric_obj['key'] = health_metrics_map[metric]['key']
            metric_obj['val'] = health_metrics_map[metric]['val']
            metric_obj['frmt_val'] = health_metrics_map[metric]['frmt_val']
            metrics_result.update({metric_obj['key']: metric_obj})
    return metrics_result

def _process_metric_line(line):
    if line is None:
        return None, None

    supportedMetrics = ["Scanned directories","Scanned files","Infected files","Data scanned","Time"]

    parts = line.split(':')
    if len(parts) != 2:
        return None, None

    name = parts[0].strip()
    if name.lower() not in (x.lower() for x in supportedMetrics):
        return None, None

    name = name.lower().replace(" ","_")
    val = parts[1].strip()
    if val.isdigit():
        v = int(val)
        val = v

    return name, val

def _process_file_line(line, ref_path):
    if line is None:
        return None

    parts = line.split(" ")
    if len(parts) != 3:
        return None

    result = {}
    file_name = parts[0][:-1]
    p = file_name.find(ref_path)
    if p >= 0:
        file_name = file_name[p:]

    result['filename'] = file_name
    result['virus'] = parts[1]
    return result

def runVirusScan(repo):
    ownerName = repo['sourceData']['owner']['name']
    repoName = repo['sourceData']['name']

    target = expanduser("~") + '/cloned_projects/' + ownerName + '/' + repoName

    print('Running VScan on ' + target)
    proc = Popen(['clamscan', '-i', '-o', '-r', target], stdin=PIPE, stdout=PIPE, stderr=PIPE, encoding='utf8')
    output, err = proc.communicate()

    print('Output content [' + ownerName + ':' + repoName + ']: ' + str(output) + '\r\n')
    print('Err content [' + ownerName + ':' + repoName + ']: ' + str(err) + '\r\n')


    lines = output.splitlines()
    if len(lines) <= 0:
        return None

    result = {}
    files = []
    metrics = False
    for line in lines:
        if not metrics:
            if "FOUND" in line:
                pline = _process_file_line(line, ref_path)
                if pline is None:
                    continue
                files.append(pline)
            if "SCAN SUMMARY" in line:
                metrics = True
                continue
        else:
            mName, mValue = _process_metric_line(line)
            if mName is None:
                continue
            result[mName] = mValue
    result['lastScan'] = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    result['reportedFiles'] = files
    return result

def sendSlackNotification(message):
    header = {'Content-type': 'application/json'}
    payload = '{"text":"' + os.environ['ENVIRONMENT_NAME'] + ' | ' + message + '"}'
    slack_response = requests.post(os.environ['SLACK_WEBHOOK_URL'], data=payload, headers=header)


if __name__ == "__main__":

    reposToIngest = getReposToIngest()
    ingestedRepos = ingestRepos(reposToIngest)
    writeToElasticSearch(ingestedRepos)
    

    print ("Donions!")