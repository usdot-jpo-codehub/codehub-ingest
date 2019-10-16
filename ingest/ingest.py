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


with open("config.yml", 'r') as stream:
    config = yaml.load(stream, Loader=yaml.FullLoader)

# orgs = config['orgs']
# ind_repos = config['individual_repos']

cloned_project_path = expanduser("~") + '/cloned_projects'

# >>>>>> TODO: replace get_org_repos() with function that calls ES and retrieves list of repos and associated ETags.
#  using the returned ETAGs, make conditional calls to Github to request repos for processing.
#  From there, the rest of the code should be plug and play

# def get_org_repos():
#     org_repos = []
#     # for org in orgs:
#     #     org_repos_response = requests.get('https://api.github.com/orgs/' + org + '/repos?access_token='+os.environ['GITHUB_ACCESS_TOKEN'])
#     #     org_repos = org_repos + json.loads(org_repos_response.text)

#     for ind in ind_repos:
#         response = requests.get('https://api.github.com/repos/' + ind + '?access_token='+os.environ['GITHUB_ACCESS_TOKEN'])
#         ind_repo = []
#         ind_repo.append(json.loads(response.text))
#         org_repos = org_repos + ind_repo
#     return org_repos

def map_repo_attributes(org_repos):
    repos = []
    for org_repo in org_repos:

        clone_dir = cloned_project_path+'/'+org_repo['owner']['login']+'/'+org_repo['name']
        git_url = org_repo['clone_url']
        adjusted_url = git_url.replace('https://','https://' + os.environ['GITHUB_USER'] + ':' + os.environ['GITHUB_ACCESS_TOKEN']+'@')

        org_obj = {}
        org_obj['organization'] = str(org_repo['owner']['login'])
        org_obj['organization_url'] = str(org_repo['owner']['html_url'])
        org_obj['org_avatar_url'] = str(org_repo['owner']['avatar_url'])
        org_obj['org_type'] = str(org_repo['owner']['type'])

        ##### GITHUB SPECIFIC FIELDS#########

        repo = {}
        repo['_id'] = str(org_repo['owner']['id'])+'_'+str(org_repo['id'])
        repo['org_obj'] = org_obj
        repo['env'] = 'PUBLIC'
        repo['project_name'] = org_repo['name']
        repo['html_url'] = org_repo['html_url']
        repo['description'] = org_repo['description']
        repo['language'] = org_repo['language']
        repo['stargazers'] = org_repo['stargazers_count']
        repo['forksJson'] = getForks(json.loads(get_github_property(org_repo, 'forks')))
        repo['releasesJson'] = getReleases(json.loads(get_github_property(org_repo, 'releases')))
        repo['pushed_at'] = org_repo['pushed_at']
        repo['created_at'] = org_repo['created_at']
        repo['contributors'] = getRepoContributions(json.loads(get_github_property(org_repo, 'contributors')))['contributorsMap']
        repo['languagesJson'] = json.loads(get_github_property(org_repo, 'languages'))
        readmeobj = json.loads(get_github_property(org_repo, 'readme'))
        if 'content' in readmeobj:
            decoded_readme = str(base64.b64decode(readmeobj['content']),'utf-8')
            readmeobj['content'] = decoded_readme
            repo['readmeRaw'] = readmeobj
        else:
            repo['readmeRaw'] = {'content': '', 'url': ''}
        repo['numWatchers'] = len(json.loads(get_github_property(org_repo, 'subscribers')))
        repo['contributorsCount'] = len(repo['contributors'])
        repo['numCommits'] = getRepoContributions(json.loads(get_github_property(org_repo, 'contributors')))['commitTotal']
        repo['calculatedRank'] = calculateRanks(int(repo['stargazers']), int(repo['numWatchers']), int(repo['contributorsCount']), int(repo['numCommits']))
        repo['autosuggest'] = []
        repo['org'] = org_repo['owner']['login']
        repo['cloned_project_path'] = clone_dir 
        repo['clone_url'] = adjusted_url
        repos.append(repo)
    return repos

def calculateRanks(stargazers_count, watchers_count, contributors_count, commit_count):
    result = (stargazers_count*3) + (watchers_count*4) + (contributors_count*5) + commit_count
    return result

def getAutoSuggestFields(repoName, repoDesc, orgName, languages, contributors):
    contributorsList = []
    for contributor in contributors:
        contributorsList.append(contributors['login'])

def getReleases(releasesJson):
    results = []
    for release in releasesJson:
        result = {}
        result['tag_name'] = release['tag_name']
        result['name'] = release['name']
        result['id'] = release['id']
        # none of the test cases currently have assets or download counts. Will test this later
        result['assets'] = []
        result['downloads'] = 0
        results.append(result)
    return results

def getForks(forksJson):
    result = []
    for fork in forksJson:
        repo = {}
        repo['id'] = str(fork['owner']['id']) + '-' + str(fork['id'])
        repo['name'] = str(fork['name'])
        repo['org_name'] = str(fork['owner']['login'])
        result.append(repo)
    return result

def getRepoContributions(contributorsJson):
    commitTotal = 0
    contributors = []
    for contributorJson in contributorsJson:
        commitTotal += contributorJson['contributions']
        contributor = {}
        contributor['user_type'] = contributorJson['type']
        if(contributorJson['type']=='User'):
            contributor['username'] = contributorJson['login']
            contributor['profile_url'] = contributorJson['html_url']
            contributor['avatar_url'] = contributorJson['avatar_url']
        else:
            contributor['username'] = ''
            contributor['profile_url'] = ''
            contributor['avatar_url'] = ''
        contributors.append(contributor)
    contributionMap = {'commitTotal': commitTotal, 'contributorsMap': contributors}
    return contributionMap

def get_github_property(repo, property_name):
    org = repo['owner']['login']
    name = repo['name']
    return requests.get('https://api.github.com/repos/' + org + '/' + name + '/' + property_name + '?access_token='+os.environ['GITHUB_ACCESS_TOKEN']).text

def clone_repos(repos):
  for repo in repos:
    setup_cloning_dir(repo['org'], repo['project_name'])
    call(["git","clone",repo['clone_url']])

def setup_cloning_dir(org, repo):
    orgdir = cloned_project_path + '/' + org
    repodir = orgdir + '/' + repo
    if os.path.exists(repodir):
        shutil.rmtree(repodir)
    if os.path.exists(orgdir):
        os.chdir(orgdir)
    else:
        os.makedirs(orgdir)
        os.chdir(orgdir)

def execute_sonar(repo):    

    exclusions = '**/system/**, **/test/**, **/img/**, **/logs/**, **/fonts/**, **/generated-sources/**, **/packages/**, **/docs/**, **/node_modules/**, **/bower_components/**,**/dist/**,**/unity.js,**/bootstrap.css, **/tools/**'

    file_object = open(repo['cloned_project_path']+"/sonar-project.properties", 'w')

    file_object.write("sonar.projectKey="+repo['org'] + ":" + repo['project_name'])
    file_object.write("\n")
    file_object.write("sonar.projectName="+repo['project_name']+" of "+repo["org"])
    file_object.write("\n")
    file_object.write("sonar.projectVersion=1.0")
    file_object.write("\n")
    file_object.write("sonar.sources="+repo['cloned_project_path'])
    file_object.write("\n")
    file_object.write("sonar.exclusions=file:"+exclusions)
    file_object.write("\n")
    file_object.write("sonar.sourceEncoding=UTF-8")
    file_object.close()
    
    curr_dir = os.getcwd()
    os.chdir(repo['cloned_project_path'])
    call('pwd')
    call(config['sonar_runner_path'], shell=True)
    os.chdir(curr_dir)


def get_sonar_metrics(repo):
    metrics_list = config['sonar_health_metrics']
    health_metrics_map = {}

    res = '_response'
    for metric in metrics_list:
        returned_res = requests.get(os.environ['SONAR_API_BASE_URL']+'/api/resources?resource='+repo['org']+':'+repo['project_name']+"&metrics="+metric, auth=('admin', 'admin'))
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
                print ('Health metrics not found for ' + repo['org']+'/'+repo['project_name'])
                health_metrics_map[metric] = {}
    metrics_result = {}
    for metric in health_metrics_map:
        if 'key' in health_metrics_map[metric]:
            metrics_result.update({health_metrics_map[metric]['key']: health_metrics_map[metric]})
    repo['metrics'] = metrics_result
    return repo

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

def runVirusScan(target):
    print('Running VScan on ' + target)
    proc = Popen(['clamscan', '-i', '-o', '-r', target], stdin=PIPE, stdout=PIPE, stderr=PIPE, encoding='utf8')
    output, err = proc.communicate()

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
    result['lastscan'] = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    result['reported_files'] = files
    return result

def getESCodeOutput(repo_json):
    result = {}
    result['created_at'] = repo_json['created_at']
    result['language'] = repo_json['language']
    result['metrics'] = repo_json['metrics']
    result['organization'] = repo_json['org_obj']
    result['origin'] = 'PUBLIC'
    result['project_name'] = repo_json['project_name']
    result['stage_id'] = repo_json['_id']
    result['stage_source'] = "SONAR"
    result['updated_at'] = repo_json['pushed_at']
    return json.dumps(result)

def getESProjectOutput(repo_json):
    vsResults = runVirusScan(repo_json['cloned_project_path'])
    
    result = {}
    result['vscan'] = vsResults
    result['commits'] = repo_json['numCommits']
    result['contributors'] = repo_json['contributorsCount']
    result['contributors_list'] = repo_json['contributors']
    result['created_at'] = repo_json['created_at']
    result['forks'] = {'forkedRepos': repo_json['forksJson']}
    result['full_name'] = repo_json['org_obj']['organization'] + '/' + repo_json['project_name']
    result['language'] = repo_json['language']
    result['languages'] = repo_json['languagesJson']
    result['organization'] = repo_json['org_obj']
    result['origin'] = 'PUBLIC'
    result['project_description'] = repo_json['description']
    result['project_name'] = repo_json['project_name']
    result['rank'] = repo_json['calculatedRank']
    result['readMe'] = {'content': repo_json['readmeRaw']['content'], 'url': repo_json['readmeRaw']['url']}
    result['releases'] = []
    result['repository'] = repo_json['project_name']
    result['repository_url'] = repo_json['html_url']
    result['stage_id'] = repo_json['_id']
    result['stars'] = repo_json['stargazers']
    result['suggest'] = []
    result['updated_at'] = repo_json['pushed_at']
    result['watchers'] = repo_json['numWatchers']

    return json.dumps(result)

def createESInsertString(repo_json, index):
    idstr = json.loads(repo_json)['stage_id']
    return '{"index": {"_index": "' + index + '", "_id": "' + idstr + '"}}'

if __name__ == "__main__":
    updated_repos = []
    update_document = ''
    repo_list_resp = requests.get(os.environ['ELASTICSEARCH_API_BASE_URL'] + '/repos/_search')
    repo_list_json = json.loads(repo_list_resp.text)['hits']['hits']
    for repojson in repo_list_json:
        repo_name = repojson['_source']['repo']
        repo_etag = repojson['_source']['etag']
        ghresponse = requests.get('https://api.github.com/repos/' + repo_name + '?access_token='+os.environ['GITHUB_ACCESS_TOKEN'], headers={'If-None-Match': repo_etag})
        if (ghresponse.headers['Status'] != '304 Not Modified'):
            print("Adding " + repo_name + " to batch and updating etag")
            update_document += '{"index": {"_index": "repos", "_id": "' + repo_name + '"}} \r\n'
            update_document += json.dumps({'repo': repo_name, 'etag': ghresponse.headers['ETag']}) + '\r\n'
            
            updated_repos.append(json.loads(ghresponse.text))
        else:
            print("Repo " + repo_name + " already up to date. Skipping...")

    document = ''
    repos = map_repo_attributes(updated_repos)
    clone_repos(repos)
    for repo in repos:
        print('Processing ' + repo['project_name'])
        execute_sonar(repo)
        # Waiting 5 sec to allow sonar to process results before querying
        time.sleep(5)
        repo_with_metrics = get_sonar_metrics(repo)

        es_code_json = getESCodeOutput(repo_with_metrics)
        es_project_json = getESProjectOutput(repo)

        document += createESInsertString(es_code_json, 'code') + '\r\n'
        document += es_code_json + '\r\n'
        document += createESInsertString(es_project_json, 'projects') + '\r\n'
        document += es_project_json + '\r\n'

        print(repo['project_name'] + ' processed')

    # # # send to ES
    if(document != ''):
        print('Writing data to ES')
        header = {'Content-type': 'application/json'}
        es_post_response = requests.post(os.environ['ELASTICSEARCH_API_BASE_URL'] + '/_bulk', data=document, headers=header)
        print('Data written to ES')
        print(es_post_response.text)

    else:
        print('Elasticsearch already up to date.')

    if(update_document != ''):
        print('Updating Local ETags')
        header = {'Content-type': 'application/json'}
        es_post_response = requests.post(os.environ['ELASTICSEARCH_API_BASE_URL'] + '/_bulk', data=update_document, headers=header)
        print('Data written to ES')
        print(es_post_response.text)

    print ("Donions!")