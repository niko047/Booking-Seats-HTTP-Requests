#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Sep 10 16:32:57 2020

@author: niccolodiana
"""

#Importing some important stuff
import requests
import datetime
from pytz import timezone
import json
import time
from multiprocessing import Process
import schedule
import random

#Retrieve from a document all ids and passwords
#DO - Create a "credentials.txt" to store id e pw
with open('credentials.txt') as f:
    credentials = [line.rstrip() for line in f]
    f.close()
    
tables=['1759','1766','1829','1838','1847','1856','1865','1874','1883','1892','1901','1910',
               '1773','1919','1928','1937','1946','1780','1787','1794','1801','1808','1815','1822',
               '1956','1963','1970']

class BocconiUser:
    
    def __init__(self, username, password, indexPreference):
        #future plans, preferences of seats
        self.indexPreference = indexPreference
        
        #Id and Pw for login
        self.username = username
        self.password = password
        
        #Statuses
        self.statusBookSeat = None
        self.statusCheckIn = None
        self.booked = False
        
        #Auth token gotten once the user logs in with the requests session
        self.authToken = ''
        
        #Creates a session object with the requests module to store cookies and maintain a "human-like feel" in making requests, also keeps an Alive-Session
        self.session = requests.Session()
        
        #Potential errors get recorded here
        self.error = None
        self.lastResponse=None
        
        #Headers for all post requests, always the same and do not need further modifications
        self.headers = {'Referer': 'https://studyseatspwa-prd.eu-de.mybluemix.net/',
                 'Content-Type': 'application/json',
                 'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.83 Safari/537.36',
                 'Accept': 'application/json, text/plain, */*'}
        
        #information of the seats
        self.infos = {
                
                0: { 'seatLocation' : 'SA.F0.A1.T4.S7',
                     'seatQrCode' : 'fd365ef1-041b-484c-a9a0-3d09cd5e678e',
                     'seatAssetId' : '1145',
                     'bookedByThirds' : False,
                     'bookedByUs' : False },
                
                1: { 'seatLocation' : 'G1.F-1.A1.T17.S2',
                     'seatQrCode' : 'a6491565-350a-46ab-b9dd-eeed29161986',
                     'seatAssetId' : '1895',
                     'bookedByThirds' : False,
                     'bookedByUs' : False },
                2: {
                    'seatLocation' : 'G1.F-1.A1.T19.S5',
                    'seatQrCode' : 'dc42ef51-8b4d-481f-b245-d7bcd0fb2fd7',
                    'seatAssetId' : '1911',
                    'bookedByThirds' : False,
                    'bookedByUs' : False },
                3 : {
                    'seatLocation' : 'G1.F-1.A1.T21.S0',
                    'seatQrCode' : '070ba736-bb0d-4c5c-957b-ac0477594755',
                    'seatAssetId' : '1929',
                    'bookedByThirds' : False,
                    'bookedByUs' : False 
                    }
                }
                
        self.resDict = {}
        self.statusSeats = {}
        self.lastBooking = None
    
    #main function at the core of the class
    def main(self):
        
        self.logIn()
        self.bookSeat()
        
    #Get the current time, shape it into the required API format and attach it to request
    def getCurrentTime(self):
        
        #Formats the time in the following way (required when making request) : "2020-09-14T15:29:40.844607+02:00"
        rome = timezone('Europe/Rome')
        now = datetime.datetime.now(rome)
        return "%s:%.3f%s" % (
            now.strftime('%Y-%m-%dT%H:%M'),
            float("%.3f" % (now.second + now.microsecond / 1e6)),
            '+01:00')
    
    def logIn(self):
        #Creates a Requests session object to keep an Alive-Connection
        
        data = '{ "email" :"' + str(self.username) + '", "password":"' + str(self.password) + '"}'
        
        response = self.session.post('https://k8studyseatsapi-prd-682c8f8095f38fab2624b89493871c79-0000.eu-de.containers.appdomain.cloud/api/v1/login',
                      headers=self.headers,
                      data=data)
        #returns an touple with an authorization token paired with a login id
        self.authToken = response.headers['Authorization'][7:]
        
    def getTableStatus(self, table_n='1910'):
        url = 'https://k8studyseatsapi-prd-682c8f8095f38fab2624b89493871c79-0000.eu-de.containers.appdomain.cloud/api/v1/tables/'+table_n+'/state?access_token='+self.authToken
        statusTable = self.session.get(url, headers=self.headers)
        for i in range(0, len(dict(statusTable.json())['seats'])):
            self.statusSeats['S'+str(i)] = dict(statusTable.json())['seats'][i]['state']
        print(self.statusSeats)
    
    def is_booking_active(self):
        #Check if reservation is about to expire, and if so extend it
        url_current_bookings = 'https://k8studyseatsapi-prd-682c8f8095f38fab2624b89493871c79-0000.eu-de.containers.appdomain.cloud/api/v1/reservations/me?access_token=eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIzMDQ1NjE2IiwiZXhwIjoxNjE0NDIxNTg0LCJhdXRob3JpdGllcyI6W3siYXV0aG9yaXR5IjoiU1RVREVOVCJ9XX0.tNIzHpI8peW4R-mls2BDH8xG550xgci8HaVMARSsPYI'
        statusTable = self.session.get(url_current_bookings, headers=self.headers)
        self.lastBooking = list(statusTable.json())[0]['active']
        self.booking_id = list(statusTable.json())[0]['asset']['area']['id']
        print('Am I currently booking a seat?',self.lastBooking)
    
    def bookSeat(self):
        #Prepares the data, url and header of the post request to book the seat for 15 minutes, before check-in
        
        data = '{"attendees":[],"name":"reservation for asset' + str(self.infos[self.indexPreference]['seatAssetId']) + '","assetId":'+self.infos[self.indexPreference]['seatAssetId'] + ',"start":"'+self.getCurrentTime()+'","assetType":"SEAT"}'
        url = 'https://k8studyseatsapi-prd-682c8f8095f38fab2624b89493871c79-0000.eu-de.containers.appdomain.cloud/api/v1/reservations/me?access_token='+str(self.authToken)
        response = self.session.post(url, data=data, headers=self.headers)

        #see statuses
        #Handle response 400 -  Already Booked
        #Handle response 403 - Reservation Overlaps with another one

        #To-do Next: handle the hypotetical case where 1) seat is booked and 2) temporary error in booking

        resText = json.loads(response.text)
        self.lastResponse = response
        
        if response.status_code not in range(200,299):
            #OOps, something is not working as expected
            #change the 
            self.statusBookSeat = False
        else:
            #It did work, do something about it, check in next
            self.resDict = json.loads(response.text) if type(json.loads(response.text)) == dict else None
            time.sleep(10)
            self.scanQrCode()

    def scanQrCode(self):
        
        if self.error != None:
            self.error = None
            return
        #Prepares the new url with the reservationId inside the query
        url = 'https://k8studyseatsapi-prd-682c8f8095f38fab2624b89493871c79-0000.eu-de.containers.appdomain.cloud/api/v1/reservations/me/'+str(self.resDict['id'])+'/check-in?access_token='+str(self.authToken)

        #Sends the post request to confirm the check-in, meaning it "scans the QR code through a post request"
        response = self.session.post(url, data=self.infos[self.indexPreference]['seatQrCode'], headers = self.headers)
        
        self.statusCheckIn = str(response.status_code)
        self.statusBookSeat = True
        
        print("STATUS CHECK IN: ", self.statusBookSeat)
    
        


class MultiprocessingSeats:
    
    def __init__(self, studentObjects):
        
        self.studentObjects = studentObjects
        self.statuses = [(stud, stud.statusBookSeat) for stud in studentObjects] #copies in memory
    
    #run all processes, meaning do that for all ids in the credentials.txt
    def runAllProcesses(self):
        
        procs = []
        
        for stud in self.studentObjects:
            print('STATUS BOOKED', stud.booked)
            if not stud.booked:
                proc = Process(target = stud.main)
                procs.append(proc)
                proc.start()
                print(datetime.datetime.now())
        for proc in procs:
            proc.join()
    
    #it might not work at the first round, do that again at random intervals
    def runUntilComplete(self):
        print('Sanity check', list(dict.fromkeys([stud.booked for stud in self.studentObjects])))
        
        #Problem here is that it shouldn't detect only True or False but should identify one of three cases:
        #1. The seat is already booked by me
        #2. The seat is already booked by third parties
        #3. The building is closed and reservation cannot be carried out
        while list(dict.fromkeys([stud.booked for stud in self.studentObjects])) != True:
            self.runAllProcesses()
            time.sleep(random.randint(5,8))
            
#Objects creation reflecting users
nico = BocconiUser(credentials[0], credentials[1], 3)

#Multiprocessing, takes the available CPUs so that requests for every user run simultaniously
#UNCOMMENT BELOW
processing = MultiprocessingSeats([nico]) #Eventually modify with a set of users


#For the multiprocessing to work needs to be initialized from terminal as $python3 reserver2020.py
#Build a database containing the different opening and closing times for the different Bocconi buildings
#UNCOMMENT BELOW
opening_time = "08:30"
schedule.every().day.at(opening_time).do(nico.main())

if __name__ == '__main__':
    while True:
        schedule.run_pending()
        time.sleep(10)
