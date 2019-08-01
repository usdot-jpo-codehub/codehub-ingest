import yaml
import requests
import json
import os
from os.path import expanduser
from subprocess import call,check_output
import subprocess
import json,pickle
import shutil 
import glob2
import boto3


with open("config.yml", 'r') as stream:
    config = yaml.load(stream, Loader=yaml.FullLoader)

orgs = config['orgs']
cloned_project_path = expanduser("~") + '/cloned_projects'

def get_org_repos():
    org_repos = []

    # for each org, get a list of all repos
    for org in orgs:
        org_repos_response = requests.get('https://api.github.com/orgs/' + org + '/repos?access_token='+config['github_access_token'])
        org_repos = org_repos + json.loads(org_repos_response.text)

    return org_repos

def map_repo_attributes(org_repos):
    repos = []
    for org_repo in org_repos:
        clone_dir = cloned_project_path+'/'+org_repo['owner']['login']+'/'+org_repo['name']
        repo = {}
        git_url = org_repo['clone_url']
        
        adjusted_url = git_url.replace('https://','https://' + config['github_user'] + ':' + config['github_access_token']+'@')

        repo['_id'] = str(org_repo['owner']['id'])+'_'+str(org_repo['id'])
        repo['project_name'] = org_repo['name']
        repo['clone_url'] = adjusted_url
        repo['language'] = org_repo['language']
        repo['org'] = org_repo['owner']['login']
        repo['cloned_project_path'] = clone_dir
        repos.append(repo)
    return repos

def clone_repos(repos):
  for repo in repos:
    setup_cloning_dir(repo['org'], repo['project_name'])
    call(["git","clone",repo['clone_url']])

def process_cloned_project(repo):
    repo_map = {}
    if "cloned_project_path" in repo and repo["cloned_project_path"] is not None:
        src_dir = repo['cloned_project_path']+'/*/'
        lists = glob2.glob(src_dir)
        if(len(lists) > 0):
            repo_map['_id'] = repo['_id']
            repo_map['project_name'] = repo['project_name']
            repo_map['src_list'] = lists
            repo_map['org'] = repo['org']
            repo_map['language'] = repo['language']
            repo_map['root_dir'] = repo['cloned_project_path']
    return repo_map
        

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
    aggregated_src = ''
    exclusions = '**/system/**, **/test/**, **/img/**, **/logs/**, **/fonts/**, **/generated-sources/**, **/packages/**, **/docs/**, **/node_modules/**, **/bower_components/**,**/dist/**,**/unity.js,**/bootstrap.css, **/tools/**'
    for src in repo['src_list']:
        aggregated_src = src + "," + aggregated_src
    print("Building sonar configuration file...")
    print(repo)
    file_object = open(repo['root_dir']+"/sonar-project.properties", 'w')
    file_object.write("sonar.projectKey="+repo['org'] + ":" + repo['project_name'])
    file_object.write("\n")
    file_object.write("sonar.projectName="+repo['project_name']+" of "+repo["org"])
    file_object.write("\n")
    file_object.write("sonar.projectVersion=1.0")
    file_object.write("\n")
    file_object.write("sonar.sources="+aggregated_src)
    file_object.write("\n")
    file_object.write("sonar.exclusions=file:"+exclusions)
    file_object.write("\n")
    file_object.write("sonar.sourceEncoding=UTF-8")
    file_object.close()
    
    curr_dir = os.getcwd()
    os.chdir(repo['root_dir'])
    call('pwd')
    call(config['sonar_runner_path'], shell=True)
    os.chdir(curr_dir)


def get_sonar_metrics(repo):
    metrics_list = config['sonar_health_metrics']
    health_metrics_map = {}

    res = '_response'
    for metric in metrics_list:
        returned_res = requests.get(config['sonar_api_local_base_url']+'?resource='+repo['org']+':'+repo['project_name']+"&metrics="+metric)
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
                health_metrics_map[metric] = {}
    repo['metrics'] = health_metrics_map
    return repo


def publish_to_sqs(repo_json):
    sqs = boto3.client('sqs')
    queue_url = config['sqs_queue']
    response = sqs.send_message(QueueUrl=queue_url,MessageBody=repo_json)
    print(response)

if __name__ == "__main__":
    org_repos = get_org_repos()
    repos = map_repo_attributes(org_repos)
    clone_repos(repos)
    for repo in repos:
        processed_repo = process_cloned_project(repo)
        if bool(processed_repo):
            execute_sonar(processed_repo)
            filtered_repo = get_sonar_metrics(processed_repo)
            print(filtered_repo)
            publish_to_sqs(str(filtered_repo))
    print ("Done")