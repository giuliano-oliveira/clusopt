from clusopt_core.cluster import CluStream,Streamkm
from sklearn.cluster import KMeans,MiniBatchKMeans

from abc import ABC,abstractmethod

class StaticGeneric(ABC):

	# batch_size and NAME members are abstract

	def __init__(self,repetitions,seed,k,chunk_size):
		self.chunk_size=chunk_size
		self.repetitions=repetitions
		self.seed=seed
		self.k=k

	@abstractmethod
	def partial_fit(self,chunk):pass

	@abstractmethod
	def get_partial_cluster_centers(self):pass

	@abstractmethod
	#should return (center,labels)
	def get_final_cluster_centers(self)->tuple:pass

class StaticClustream(StaticGeneric):
	NAME="clustream"

	def __init__(self,*args,window_range,microclusters,kernel_radius,**kwargs):
		super().__init__(*args,**kwargs)
		self.batch_size=microclusters
		self.model=CluStream(
			h=window_range,
			m=microclusters,
			t=kernel_radius
		)
		self.initted=False
		self.macro_model=KMeans(
			init="k-means++",
	 		random_state=self.seed,
	 		n_clusters=self.k,
	 		n_init=self.repetitions,
	 	)

	def partial_fit(self,chunk):
		if self.initted:
			self.model.partial_fit(chunk)
		else:
			self.model.init_offline(chunk,self.seed)
			self.initted=True
		self.__micro_clusters=self.model.get_kernel_centers()
		self.__macro_labels=self.macro_model.fit_predict(self.__micro_clusters)
		self.__macro_clusters=self.macro_model.cluster_centers_

	def get_partial_cluster_centers(self):
		return self.__micro_clusters

	def get_final_cluster_centers(self):
		return self.__macro_clusters,self.__macro_labels

class StaticStreamkm(StaticGeneric):
	NAME="streamkm"
	def __init__(self,*args,coresetsize,length,**kwargs):
		super().__init__(*args,**kwargs)
		self.batch_size=coresetsize

		self.model=Streamkm(
			coresetsize=coresetsize,
			length=length,
			seed=self.seed
		)
		self.macro_model=KMeans(
			init="k-means++",
	 		random_state=self.seed,
	 		n_clusters=self.k,
	 		n_init=self.repetitions,
	 	)

	def partial_fit(self,chunk):
		self.model.partial_fit(chunk)
		self.__coresets=self.model.get_streaming_coreset_centers()

		self.__macro_labels=self.macro_model.fit_predict(self.__coresets)
		self.__macro_clusters=self.macro_model.cluster_centers_

	def get_partial_cluster_centers(self):
		return self.__coresets

	def get_final_cluster_centers(self):
		return self.__macro_clusters,self.__macro_labels

class StaticMinibatch(StaticGeneric):
	NAME="minibatch"
	def __init__(self,*args,**kwargs):
		super().__init__(*args,**kwargs)
		self.batch_size=self.chunk_size

		self.model=MiniBatchKMeans(
			random_state=self.seed,
			batch_size=self.chunk_size,
			n_init=self.repetitions,
			n_clusters=self.k,
			compute_labels=True,
		)

	def partial_fit(self,chunk):
		self.model.partial_fit(chunk)
		self.__last_chunk=chunk

	def get_partial_cluster_centers(self):
		return self.__last_chunk

	def get_final_cluster_centers(self):
		return self.model.cluster_centers_,self.model.labels_


class StaticMinibatchSplit(StaticGeneric):
	NAME="minibatchsplit"
	def __init__(self,*args,microclusters,**kwargs):
		super().__init__(*args,**kwargs)
		self.batch_size=microclusters

		self.model=MiniBatchKMeans(
			batch_size=self.chunk_size,
			n_clusters=microclusters,
			init_size=self.chunk_size,
			compute_labels=False,
			random_state=self.seed
		)
		self.macro_model=KMeans(
			init="k-means++",
	 		random_state=self.seed,
	 		n_clusters=self.k,
	 		n_init=self.repetitions
	 	)

	def partial_fit(self,chunk):
		self.model.partial_fit(chunk)
		self.__micro_clusters=self.model.cluster_centers_

		self.__macro_labels=self.macro_model.fit_predict(self.__micro_clusters)
		self.__macro_clusters=self.macro_model.cluster_centers_

	def get_partial_cluster_centers(self):
		return self.__micro_clusters

	def get_final_cluster_centers(self):
		return self.__macro_clusters,self.__macro_labels