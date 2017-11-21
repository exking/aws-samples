from __future__ import print_function

from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from datetime import datetime

import boto3
import email
import urllib
import os
import re
import cStringIO
import json

rekognition = boto3.client('rekognition')
ses = boto3.client('ses')
s3 = boto3.client('s3')

def print_with_timestamp(*args):
	print(datetime.utcnow().isoformat(), *args)
	
def extract_first_image(bucket, key):
	fh = cStringIO.StringIO()
	s3.download_fileobj(bucket, key, fh)	
	mail = email.message_from_string(fh.getvalue())
	fh.close()
	
	image_fh = []
	file_num = 0
	
	for part in mail.walk():
		c_type = part.get_content_type()
		if (c_type == "image/jpeg"):
			image_fh.append(cStringIO.StringIO())
			image_fh[file_num].write(part.get_payload(None, True))
			file_num += 1

	return image_fh

def detect_labels(image_file):
	response = rekognition.detect_labels(
		Image = { 'Bytes': image_file.getvalue(), },
		MaxLabels = 10,
		MinConfidence = 80,
	)
	return response['Labels']
	
def send_email(mail_body, image_file, mail_to):
	msg = MIMEMultipart()
	msg['Subject'] = 'Rekognition result'
	msg['From'] = '__FROM@EXAMPLE.COM__'
	msg['To'] = mail_to
	part_num = 0
	
	part = MIMEText(mail_body)
	msg.attach(part)
	
	for image_fh in image_file:
		part = MIMEApplication(image_fh.getvalue())
		part.add_header('Content-Disposition', 'attachment', filename='Image'+str(part_num)+'.jpg')
		msg.attach(part)
		part_num += 1
	
	ses.send_raw_email(
		RawMessage = {
			'Data': msg.as_string(),
		},
		Source = msg['From'],
		Destinations = [
			msg['To'],
		]
	)


def lambda_handler(event, context):
	allowed_senders = [
		"__USER1@EXAMPLE.COM__",
		"__USER2@EXAMPLE.COM__",
	]
	analysis=''
	send_notification = False
	
	print_with_timestamp('Starting - camera AI')
	
	# Retrieve information we need from the SNS notification
	message = json.loads(event['Records'][0]['Sns']['Message'])
	bucket = message['receipt']['action']['bucketName']
	key = urllib.unquote_plus(message['receipt']['action']['objectKey'].encode('utf8'))    
	match = re.search(r'[\w\.-]+@[\w\.-]+', message['mail']['commonHeaders']['from'][0])
	mail_from = match.group(0)
	
	print_with_timestamp('Mail From: ', mail_from)
	
	if mail_from in allowed_senders:
		print_with_timestamp('Processing: ', message['mail']['messageId'])
		
		image_file = extract_first_image(bucket, key)
		
		# Call rekognition DetectLabels API
		for label in detect_labels(image_file[0]):
			if (label['Name'] == 'Human') or (label['Name'] == 'Car'):
				send_notification = True
			analysis += label['Name']+' - '+str(label['Confidence'])+'\n'
		analysis += '\n'
		
		if send_notification:
			print_with_timestamp('Human detected: ', analysis)
			send_email(analysis, image_file, mail_from)
		else:
			print_with_timestamp('No humans detected: ', analysis)
		
		for image_fh in image_file:
			image_fh.close()

	else:
		print_with_timestamp('Email sender unknown')
	
	s3.delete_object(Bucket=bucket, Key=key)
