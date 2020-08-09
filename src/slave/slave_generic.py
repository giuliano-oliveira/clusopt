from .core import Clusterer
from network import Payload,PAYID
import numpy as np
from utils import get_proc_info
import zlib
class SlaveGeneric:
	"""
	Args:
		kappa (ndarray) : K's to test
		seed (int): seed to use
		repetitions (int): number of repetitions
		ghost (int or None) : if not None, enable ghost mode when batch index equals itself
		disk_cache (int or None) : enable disk cache with max memory size equal to itself
		distance_matrix_method (str) : distance matrix algorithm to use
		batch_size (int): length of each batch
	Attributes:
		
	"""
	BATCH_DTYPE=None #{float32,float64}
	ALGORITHM=None #sklearn clusterer

	def __init__(
			self,
			server,
			kappa,
			seed,
			repetitions,
			ghost,
			disk_cache,
			distance_matrix_method,
			batch_size
		):
		self.server=server
		self.kappa=kappa
		self.seed=seed
		self.repetitions=repetitions
		self.ghost=ghost
		self.disk_cache=disk_cache
		self.distance_matrix_method=distance_matrix_method
		self.batch_size=batch_size

		if self.disk_cache != None: raise NotImplemented #TODO
		self.__BATCH_PAYID={
			"float32":PAYID.compressed_float32_matrix,
			"float64":PAYID.compressed_float64_matrix,
		}[self.BATCH_DTYPE]

		
	
	def run(self):
		clusterer=Clusterer(self.ALGORITHM,self.kappa,self.distance_matrix_method,self.batch_size)
		proc_infos=[]
		#---------------------------------------------------------------------------------
		#for every payload calc sil_score
		bc=0
		while True:
			pay=self.server.recv(self.__BATCH_PAYID,PAYID.end)
			if pay.id==PAYID.end:
				print(f"ended with {bc}")
				break
			
			should_ghost=self.ghost!=None and bc>=self.ghost
			if not should_ghost:
				k,sil=clusterer.add_and_get_best_score(pay.obj)
			else:
				k,sil=self.kappa[0],-1
				#against measure
				clusterer.best_clusterers[(bc,k)]=np.array([[0]],dtype=np.float64)
				print(f"ghosted in t={bc}")
			self.server.send(Payload(PAYID.silhouette,(bc,k,sil)))
			proc_infos.append(get_proc_info())
			print(f"i am finished with t={bc}")
			bc+=1
		self.server.send(Payload(PAYID.end))
		#---------------------------------------------------------------------------------
		#check if is winner for some k and t
		while True:
			pay=self.server.recv(PAYID.results_req,PAYID.end)
			if pay.id==PAYID.end:
				break
			batch_index,k=pay.obj
			print(f"i am the winner for batch_index={batch_index} and k={k}")
			result=clusterer.get_result(batch_index,k)
			if result is None:
				self.server.send(Payload(PAYID.err))
				print(*clusterer.best_clusterers.items(),sep="\n")
				print("-"*48)
				raise RuntimeError(f"Requested batch_index,k not found ({pay.obj}), values available {list(clusterer.best_clusterers.keys())}")
			
			compressed=zlib.compress(result.tobytes(),level=1)
			self.server.send(Payload(PAYID.compressed_float64_matrix,(result.shape,compressed)))
		#---------------------------------------------------------------------------------
		#send extra info
		data=[
			dict(
				batch_counter=i,
				rss=proc_info.rss,
				data_write=proc_info.data_write,
				data_read=proc_info.data_read
			) for i,proc_info in enumerate(proc_infos)
		]
		self.server.send(Payload(PAYID.pickle,data))