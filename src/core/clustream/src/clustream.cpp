#include "clustream.hpp"

CluStream::CluStream(int h,int m,int t){
	time_window=h;
	this->m=m;
	this->t=t;
	timestamp=0;
	points_fitted=0;
	points_forgot=0;
	points_merged=0;
	dim=0;
}
void CluStream::offline_cluster(double* datapoint){
	// 0. Initialize
	if((int)kernels.size()!=m){
		kernels.push_back(Kernel(datapoint,dim,timestamp,t,m));
		return;
	}
	// 1. Determine closest kernel
	Kernel* closest_kernel = NULL;
	double min_distance = double_max;
	for ( unsigned int i = 0; i < kernels.size(); i++ ) { //O(n)
		double dist = c_distance(datapoint, &(kernels[i].center[0]),dim);
		if ( dist < min_distance ) {
			closest_kernel = &kernels[i];
			min_distance = dist;
		}
	}
	// 2. Check whether instance fits into closestKernel
	double radius=0;
	if ( closest_kernel->n == 1 ) {
			// Special case: estimate radius by determining the distance to the
			// next closest cluster
			radius = double_max;
			Point center = closest_kernel->center;
			for ( unsigned int i = 0; i < kernels.size(); i++ ) { //O(n)
				if ( &kernels[i] == closest_kernel ) {
					continue;
				}

				double dist = distance(kernels[i].center, center );
				radius = std::min( dist, radius );
			}
		} else {
			radius = closest_kernel->get_radius();
		}

		if ( min_distance < radius ) {
			// Date fits, put into kernel and be happy
			// printf("%ld fits\n",timestamp);
			points_fitted++;
			closest_kernel->insert( datapoint, timestamp );
			return;
		}

		// 3. Date does not fit, we need to free
		// some space to insert a new kernel
		long threshold = timestamp - time_window; // Kernels before this can be forgotten

		// 3.1 Try to forget old kernels
		for (unsigned int i = 0; i < kernels.size(); i++ ) {
			if ( kernels[i].get_relevance_stamp() < threshold ) {
				kernels[i] = Kernel( datapoint,dim, timestamp, t, m );
				// printf("%ld forgot kernel\n",timestamp);
				points_forgot++;
				return;
			}
		}
		// 3.2 Merge closest two kernels
		int closest_a = 0;
		int closest_b = 0;
		min_distance = double_max;
		for ( unsigned int i = 0; i < kernels.size(); i++ ) { //O(n(n+1)/2)
			Point center_a = kernels[i].center;
			for ( unsigned int j = i + 1; j < kernels.size(); j++ ) {
				double dist = distance( center_a, kernels[j].center );
				if ( dist < min_distance ) {
					min_distance = dist;
					closest_a = i;
					closest_b = j;
				}
			}
		}
		// printf("%ld merged kernel\n",timestamp);
		points_merged++;
		kernels[closest_a].add( kernels[closest_b] );
		kernels[closest_b] = Kernel( datapoint,dim, timestamp, t,  m );
}

void CluStream::batch_offline_cluster(ndarray batch){
	auto buff=batch.request();
	if(buff.ndim!=2)
		throw std::runtime_error("batch must be a matrix");
	unsigned int lines=buff.shape[0];
	if(dim==0)
		dim=buff.shape[1];
	else if(dim!=buff.shape[1])
		throw std::runtime_error("batch must have a consistent number of columns");
	double* ptr=(double*)buff.ptr;
	// for(unsigned int i=0;i<2;i++){
	// 	for(unsigned int j=0;j<dim;j++){
	// 		printf("%lf ",ptr[j]);
	// 	}
	// 	printf("\n");
	// 	ptr+=dim;
	// }
	// throw std::runtime_error("debug");
	for(unsigned int i=0;i<lines;i++){
		offline_cluster(ptr);
		timestamp++;
		ptr+=dim;
	}
}
ndarray CluStream::get_kernel_centers(){
	ndarray ans(m*dim);
	double* ptr=(double*)ans.request().ptr;
	for(Kernel kernel:kernels){
		std::copy_n(&(kernel.center[0]), dim, ptr);
		ptr+=dim;
	}
	ans.resize({(size_t)m,(size_t)dim});
	return ans;
}

double c_distance(double* a,double* b,unsigned int dim){
	double ans=0;
	for(unsigned int i=0;i<dim;i++){
		double diff=b[i]-a[i];
		ans+=diff*diff;
	}
	return sqrt(ans);
}

double distance(Point& a,Point& b){
	double ans=0;
	for(unsigned int i=0;i<a.size();i++){
		double diff=b[i]-a[i];
		ans+=diff*diff;
	}
	return sqrt(ans);
}