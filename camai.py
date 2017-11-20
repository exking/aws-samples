#!/usr/bin/env python2.7

from __future__ import print_function

from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart

import email
import sys
import boto3
import cStringIO
import smtplib

rekognition = boto3.client(
		'rekognition',
		aws_access_key_id='__AWS_ACCESS_KEY__',
		aws_secret_access_key='__AWS_SECRET_KEY__',
		region_name='__AWS_REGION__',
		)

def detect_labels(image_file):
	response = rekognition.detect_labels(
		Image = { 'Bytes': image_file.getvalue(), },
		MaxLabels = 10,
		MinConfidence = 90,
	)
	return response['Labels']

def extract_first_image(fh):
	mail = email.message_from_string(fh.read())
	image_fh = []
	file_num = 0
	
	for part in mail.walk():
		c_type = part.get_content_type()
		if (c_type == "image/jpeg"):
			image_fh.append(cStringIO.StringIO())
			image_fh[file_num].write(part.get_payload(None, True))
			file_num += 1
	return image_fh

def send_email(mail_body, image_file):
	msg = MIMEMultipart()
	msg['Subject'] = 'Rekognition result'
	msg['From'] = '__FROM@EXAMPLE.COM__'
	msg['To'] = '__TO@EXAMPLE.COM__'
	part_num = 0
	
	part = MIMEText(mail_body)
	msg.attach(part)
	
	for image_fh in image_file:
		part = MIMEApplication(image_fh.getvalue())
		part.add_header('Content-Disposition', 'attachment', filename='Image'+str(part_num)+'.jpg')
		part_num += 1
		msg.attach(part)
	
	s = smtplib.SMTP('localhost')
	s.sendmail(msg['From'], msg['To'], msg.as_string())
	s.quit()
	
def main():
	send_notification = False
	analysis = ''
	image_file = extract_first_image(sys.stdin)
	
	for label in detect_labels(image_file[0]):
		if (label['Name'] == 'Human') or (label['Name'] == 'Car'):
			send_notification = True
		analysis += label['Name']+' - '+str(label['Confidence'])+'\n'
	analysis += '\n'

	if send_notification:
		send_email(analysis, image_file)
		
	for image_fh in image_file:
		image_fh.close()
	
if __name__=="__main__":
	main()
