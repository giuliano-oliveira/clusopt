from network import ServerSocket,Payload
import json
from argparse import ArgumentParser
from threading import Thread,Lock
from collections import namedtuple
from namedlist import namedlist
from itertools import chain
from os.path import isfile
import numpy as np
import pandas
from math import sqrt,ceil

class Bucket:
	Entry=namedlist("BucketEntry",["s","k","counter","msock"])
	def __init__(self,batch_size):
		self.lock=Lock()
		self.batch_size=batch_size
		self.data={} #t -> Bucket.Entry
	def add(self,t,k,s,msock):
		with self.lock:
			entry=self.data.get(t)
			if entry==None:
				entry=Bucket.Entry(s,k,1,msock)
				self.data[t]=entry
			else:	
				entry.counter+=1
				if s>entry.s:
					#update entry
					entry.s=s
					entry.k=k
					entry.msock=msock
			n=(t+1)*self.batch_size
			return entry.counter==(ceil(sqrt(n))-1)

	def get(self,t):
		with self.lock:
			return self.data.get(t)

class Master:
	def __init__(self,**config):
		self.config=namedtuple("config",list(config.keys()))(*list(config.values()))
		#ip_str -> msock
		self.slaves={}
		#t -> msock
		self.winners={}
		self.bucket=Bucket(self.config.batch_size)
	def accept_handler(self,msock):
		msock.send(Payload(Payload.Id.k_coeficient,len(self.slaves)+2))
		self.slaves[msock.ip]=msock
		print(f"slave {msock.ip} connected")
	def silhoete_recv_handler(self,msock):
		while True:
			pay=msock.recv(Payload.Id.end,Payload.Id.silhouette)
			if pay.id==Payload.Id.end:
				break
			# t is the batch_counter
			t,k,sil=pay.obj
			print(msock.ip,t,k,round(sil,3))
			isfull=self.bucket.add(t,k,sil,msock)
			if isfull:
				bucket_winner=self.bucket.get(t)
				print("winner",bucket_winner)
				self.winners[t]=(bucket_winner.msock,bucket_winner.k)

	def replicator_send_handler(self,msock,batch):
		msock.send(Payload(Payload.Id.datapoints,batch))
	def run(self):
		config=self.config #ugly but whatever
		server=ServerSocket(3523)
		print("waiting for slaves press [CTRL+C] to exit")
		try:
			while True:
				self.accept_handler(server.accept()) #no nedd to be multithread
		except KeyboardInterrupt:
			pass
		print(end="\r")
		#---------------------------------------------------------------------------------
		#send increment
		for slave in self.slaves.values():
			slave.send(Payload(Payload.Id.k_coeficient_inc,len(self.slaves)))
		#---------------------------------------------------------------------------------
		#start silhoete receiver threads
		sil_threads=[]
		for i,slave in enumerate(self.slaves.values()):
			t=Thread(
				name=f"silhoete-{i}",
				target=Master.silhoete_recv_handler,
				args=(self,slave,)
			)
			sil_threads.append(t)
			t.start()
		#---------------------------------------------------------------------------------
		#start replicator sender threads
		repl_threads=[]
		for i,batch in enumerate(pandas.read_csv(config.input,chunksize=config.batch_size,dtype=np.float32)):
			for j,slave in enumerate(self.slaves.values()):
				t=Thread(
					name=f"Replicator-{i,j}",
					target=Master.replicator_send_handler,
					args=(self,slave,batch.values,)
				)
				repl_threads.append(t)
				t.start()
		tmax=i
		#---------------------------------------------------------------------------------
		#send end payload
		for slave in self.slaves.values():
			slave.send(Payload(Payload.Id.end))
		#---------------------------------------------------------------------------------
		#join all threads
		for t in chain(sil_threads,repl_threads):
			t.join()
		#---------------------------------------------------------------------------------
		#determine winner and request labels
		winner,winnerk=self.winners[tmax]
		slave.send(Payload(Payload.Id.labels_req,winnerk))
		print("winner label:")
		print(winner.recv(Payload.Id.labels).obj)
		#---------------------------------------------------------------------------------
		#send end payload to others
		for slave in self.slaves.values():
			if slave is not winner:
				slave.send(Payload(Payload.Id.end))
		#---------------------------------------------------------------------------------
		#close everything
		for slave in self.slaves.values():
			slave.close()

if __name__=="__main__":
	parser=ArgumentParser()
	parser.add_argument("input",help="path or url of the comma-separated dataset")
	args=parser.parse_args()
	if not isfile(args.input):
		raise FileNotFoundError(args.input)
	with open("config.json") as f:
		config=json.load(f)
	config=dict(**vars(args),**config)
	Master(**config).run()