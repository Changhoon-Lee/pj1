#include <chrono>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <string>
#include <sys/mman.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <vector>
struct Map{int fd=-1;size_t n=0;const uint8_t*p=nullptr;~Map(){if(p&&p!=MAP_FAILED)munmap((void*)p,n);if(fd>=0)close(fd);}};
Map mapf(const std::string&s){Map m;m.fd=open(s.c_str(),O_RDONLY);if(m.fd<0){perror("open");exit(2);}struct stat st{};fstat(m.fd,&st);m.n=st.st_size;m.p=(const uint8_t*)mmap(nullptr,m.n,PROT_READ,MAP_PRIVATE,m.fd,0);if(m.p==MAP_FAILED){perror("mmap");exit(2);}return m;}
inline bool bit(const uint8_t*p,uint64_t i){return(p[i>>3]>>(i&7))&1;}
inline double Phi(double x){return .5*(1+std::erf(x/std::sqrt(2.0)));}
inline double pv(int n,int z){if(z<=0)return 1.;double sq=std::sqrt((double)n),s1=0,s2=0;int a=(int)std::floor((-n/(double)z+1)/4),b=(int)std::floor((n/(double)z-1)/4);for(int k=a;k<=b;k++)s1+=Phi((4*k+1)*z/sq)-Phi((4*k-1)*z/sq);a=(int)std::floor((-n/(double)z-3)/4);b=(int)std::floor((n/(double)z-1)/4);for(int k=a;k<=b;k++)s2+=Phi((4*k+3)*z/sq)-Phi((4*k+1)*z/sq);double p=1-s1+s2;return p<0?0:p>1?1:p;}
inline bool pass(const uint64_t*w,int nw,int n){int s=0,z=0;for(int j=0;j<nw;j++){uint64_t x=w[j];for(int b=0;b<64;b++){s+=((x>>b)&1)?1:-1;int a=s<0?-s:s;if(a>z)z=a;}}return pv(n,z)>=.01;}
std::vector<uint64_t>readidx(const std::string&p){std::ifstream f(p,std::ios::binary|std::ios::ate);size_t n=(size_t)f.tellg();f.seekg(0);std::vector<uint64_t>v(n/8);f.read((char*)v.data(),n);return v;}
int main(int ac,char**av){std::string art,rep,idxp;uint64_t N=0;int nbits=0;for(int i=1;i<ac;i++){std::string a=av[i];auto nx=[&](){return std::string(av[++i]);};if(a=="--artifact")art=nx();else if(a=="--report-pass")rep=nx();else if(a=="--indices")idxp=nx();else if(a=="--nseq")N=std::stoull(nx());else if(a=="--nbits")nbits=std::stoi(nx());else if(a=="--threads")nx();}
auto t0=std::chrono::steady_clock::now();clock_t c0=clock();Map A=mapf(art),R=mapf(rep);int nw=nbits/64;std::vector<uint64_t>idx;if(idxp.empty()){idx.resize(N);for(uint64_t i=0;i<N;i++)idx[i]=i;}else idx=readidx(idxp);uint64_t mm=0,adv=0,actual=0;
for(size_t k=0;k<idx.size();k++){uint64_t i=idx[k];bool a=pass((const uint64_t*)(A.p+(size_t)i*nw*8),nw,nbits),r=bit(R.p,i);mm+=(a!=r);adv+=(r&&!a);actual+=a;}
auto t1=std::chrono::steady_clock::now();clock_t c1=clock();struct rusage ru{};getrusage(RUSAGE_SELF,&ru);std::cout<<"{\"schema\":\"SAC_GEN5_B10_CUSUM_RECEIPT_V1\",\"audited\":"<<idx.size()<<",\"mismatches\":"<<mm<<",\"adverse_mismatches\":"<<adv<<",\"actual_pass_in_audited\":"<<actual<<",\"wall_ns\":"<<std::chrono::duration_cast<std::chrono::nanoseconds>(t1-t0).count()<<",\"cpu_ns\":"<<(long long)((double)(c1-c0)/CLOCKS_PER_SEC*1e9)<<",\"peak_rss_kib\":"<<ru.ru_maxrss<<",\"threads\":1}\n";}
