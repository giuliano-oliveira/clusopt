from threading import Lock
from utils import Timer,get_proc_info,ProgressMeter,ProcInfo
from dataclasses import dataclass
from network import Socket

@dataclass
class BucketEntry:
	sil:int
	k:int
	counter:int
	msock:Socket
	timer:Timer
	proc_info:ProcInfo

class Bucket:
	"""
	Manages each bucket entry to caclulate best silhouette for each batch index

	Args:
		batch_size (int): size of each chunk of the dataset
		total_batches (int): total number of batches
	"""
	def __init__(self,max_size,total_batches):
		self.lock=Lock()
		self.data={} #t -> Bucket.Entry
		self.max_size=max_size
		self.total_batches=total_batches
		self.progress=ProgressMeter(total_batches,"Bucket")

	def add(self,t,k,sil,msock):
		with self.lock:
			entry=self.data.get(t)
			if entry==None:#insert new entry
				entry=BucketEntry(
					sil=sil,
					k=k,
					counter=1,
					msock=msock,
					timer=Timer(),
					proc_info=get_proc_info()
				)
				self.data[t]=entry
				entry.timer.start()
			else:#update entry
				entry.counter+=1
				if sil>entry.sil:
					entry.sil=sil
					entry.k=k
					entry.msock=msock
				elif sil==entry.sil and k<=entry.k: #collision
					entry.sil=sil
					entry.k=k
					entry.msock=msock

			isfull=entry.counter==self.max_size
			if isfull:
				self.progress.update(1)
				entry.timer.stop()
			if entry.counter>self.max_size:
				raise RuntimeError("Unexpected error: bucket already full")
			return isfull
	def get(self,t):
		with self.lock:
			return self.data.get(t)
	def to_dicts(self):
		return [
			dict(
				batch_counter=t,
				silhouette=entry.sil,
				k=entry.k,
				entry_counter=entry.counter,
				time_start=entry.timer.beginning,
				time_end=entry.timer.end,
				time=entry.timer.t,
				rss=entry.proc_info.rss,
				data_write=entry.proc_info.data_write,
				data_read=entry.proc_info.data_write
			)
			for t,entry in self.data.items()
		]
		