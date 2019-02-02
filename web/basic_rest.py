#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from flask import Flask, jsonify, request
from flask_restful import Api, Resource #some classes are resource
from pymongo import MongoClient
import bcrypt
import requests
import subprocess
import json
import os 
import sys

#import logging
#logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
api = Api(app)

# =====================================================
# Database config
# =====================================================
client  = MongoClient("mongodb://db:27017")
db = client.ImageRecognition #Create a database name = SentencesDB
users = db["Users"] #assign a collection
visit_num = db["visit_num"]
#Add a document to the collection
visit_num.insert({"num_of_visits":0})


# =====================================================
# Functions
# =====================================================
def verify_pw(username,password):

    if user_exist(username):
        hashed_pw = users.find({"username":username})[0]["password"]
        if bcrypt.checkpw(password.encode('utf-8'),hashed_pw):
            return True
        else:
            return False
    else:
        return False


def count_tokens(username):
    tokens = users.find({"username":username})[0]["tokens"]
    return tokens

def user_exist(username):
    if users.find({"username":username}).count()==0:
        return False #user does not exists
    else:
        return True #user exists

def verify_credentials(username,password):
    if not user_exist(username):
        return generate_return_dictionary(301,"invalid username"), True
    
    correct_pw = verify_pw(username, password)
    if not correct_pw:
        return generate_return_dictionary(302,"invalid password"), True
    
    return None, False
    

def generate_return_dictionary(status,msg):
    retJson = {
            "status":status,
            "msg":msg
            }
    return retJson

# =====================================================
# Define Resources
# Resources are what we are offering (addition, subtraction, multiplication, division)
# =====================================================
class Visit(Resource):
    def get(self):
        prev_num = visit_num.find()[0]["num_of_visits"]
        new_num  = prev_num+1
        visit_num.update({},{"$set":{"num_of_visits":new_num}})
        return "Visit {}".format(new_num)


class Register(Resource):
    def post(self):
        '''
        it will be called when we use post method
        we reach here when resource Add was requested using post method
        '''

        postedData = request.get_json()
        #Get data (for real API have to check input validity)
        username = postedData["username"]
        password = postedData["password"]

        #Check if the username already exists
        if user_exist(username):
            retJson = {
                "status": 301,
                "msg": "Invalid username"
            }
            return jsonify(retJson)
        #Hashing the password and store in db
        hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        #store username/pass into db
        users.insert({
        			"username":username,
        			"password":hashed_pw,
                    "tokens":6
                    })

        #Return successful message
        retJson = {
                "status":200,
                "msg":"Registration was successful"
                }

        return jsonify(retJson)



class Classify(Resource):
    def post(self):
        postedData = request.get_json()
        username = postedData["username"]
        password = postedData["password"]
        url = postedData["url"]
        
        retJson, error = verify_credentials(username,password)
        if error:
            return jsonify(retJson)
        
        tokens = count_tokens(username)
        if tokens <= 0:
            return jsonify(generate_return_dictionary(status=303,msg="Not enough tokens"))
        
        r = requests.get(url)

        retJson = {}
        
        #save the image
        with open('temp.jpg','wb') as f:
            f.write(r.content)
        
        print("file list: {}".format(os.listdir()), file=sys.stderr)
        #new subprocess for classification
        proc = subprocess.Popen("python classify_image.py --model_dir=. --image_file=./temp.jpg", stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
        proc.communicate(0)
        proc.wait() #wait until the process is finished and write the prediction result into a file
            
        with open("text.json") as g:
            retJson = json.load(g)
                
        users.update({"username":username},{"$set":{"Tokens":tokens-1}})
        return retJson
            
            
        

class Refill(Resource):
    def post(self):
        postedData = request.get_json()
        username = postedData["username"]
        password = postedData["admin_pw"]
        refill_amount = postedData["refill"]

        #Check if the username is valid
        if not user_exist(username):
            return jsonify(generate_return_dictionary(status=301,msg="Invalid username"))

        #Check for correct admin password
        admin_pw = "abcabc" #better store the hashed pw in db rather than hardcoding
        if not admin_pw == password:
            return jsonify(generate_return_dictionary(status=304,msg="Invalid admin password"))


        current_tokens = count_tokens(username)
        users.update({"username":username},{"$set":{"tokens":refill_amount+current_tokens}})
        return jsonify(generate_return_dictionary(status=200,msg="refilled successfully"))

# =====================================================
# After defining resources, we need to do mapping (url)
# =====================================================

api.add_resource(Visit,"/visit")
api.add_resource(Register,"/register")
api.add_resource(Classify,"/classify")
api.add_resource(Refill,"/refill")



@app.route('/')
def hello_world():
    return ('Hello world')

if __name__ == "__main__":
    app.run(host='0.0.0.0',debug=True)
