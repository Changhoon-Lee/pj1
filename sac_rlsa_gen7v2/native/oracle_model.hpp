#pragma once
#include <algorithm>
#include <bit>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <fcntl.h>
#include <fstream>
#include <limits>
#include <stdexcept>
#include <string>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>
#include <utility>
#include <vector>

static_assert(sizeof(double)==8 && sizeof(float)==4);
static_assert(std::endian::native==std::endian::little,"little-endian artifacts required");

struct Node { int32_t left,right,feature; double threshold,value,weight; };
struct Tree { uint32_t max_depth; std::vector<Node> nodes; };
struct Model { uint32_t n_features; double learning_rate,init,raw_min,raw_max,loss_upper,reserved; std::vector<Tree> trees; };

template<class T> T read_value(std::ifstream& f){T v{};f.read(reinterpret_cast<char*>(&v),sizeof(v));if(!f)throw std::runtime_error("short model read");return v;}

inline Model load_model(const std::string& path){
 std::ifstream f(path,std::ios::binary);if(!f)throw std::runtime_error("model open");char magic[8];f.read(magic,8);
 if(std::memcmp(magic,"SACGBM2\0",8)!=0)throw std::runtime_error("model magic");
 uint32_t version=read_value<uint32_t>(f),nf=read_value<uint32_t>(f),nt=read_value<uint32_t>(f);(void)read_value<uint32_t>(f);
 if(version!=2)throw std::runtime_error("model version");Model m{};m.n_features=nf;
 m.learning_rate=read_value<double>(f);m.init=read_value<double>(f);m.raw_min=read_value<double>(f);m.raw_max=read_value<double>(f);m.loss_upper=read_value<double>(f);m.reserved=read_value<double>(f);
 for(uint32_t t=0;t<nt;++t){Tree tr{};uint32_t count=read_value<uint32_t>(f);tr.max_depth=read_value<uint32_t>(f);tr.nodes.reserve(count);
  for(uint32_t i=0;i<count;++i){Node n{};n.left=read_value<int32_t>(f);n.right=read_value<int32_t>(f);n.feature=read_value<int32_t>(f);n.threshold=read_value<double>(f);n.value=read_value<double>(f);n.weight=read_value<double>(f);tr.nodes.push_back(n);}m.trees.push_back(std::move(tr));}
 return m;
}

struct Mapping{
 int fd=-1;size_t bytes=0;void* ptr=MAP_FAILED;
 Mapping()=default;Mapping(const Mapping&)=delete;Mapping& operator=(const Mapping&)=delete;
 Mapping(Mapping&& o)noexcept:fd(o.fd),bytes(o.bytes),ptr(o.ptr){o.fd=-1;o.bytes=0;o.ptr=MAP_FAILED;}
 ~Mapping(){if(ptr!=MAP_FAILED)munmap(ptr,bytes);if(fd>=0)close(fd);}
};
inline Mapping map_file(const std::string& path){Mapping m;m.fd=open(path.c_str(),O_RDONLY);if(m.fd<0)throw std::runtime_error("open "+path);struct stat st{};if(fstat(m.fd,&st))throw std::runtime_error("stat "+path);m.bytes=static_cast<size_t>(st.st_size);m.ptr=mmap(nullptr,m.bytes,PROT_READ,MAP_PRIVATE,m.fd,0);if(m.ptr==MAP_FAILED)throw std::runtime_error("mmap "+path);return m;}
inline std::vector<uint32_t> load_indices(const std::string& path){if(path.empty())return{};std::ifstream f(path,std::ios::binary);if(!f)throw std::runtime_error("indices open");std::vector<uint32_t> v;uint32_t x;while(f.read(reinterpret_cast<char*>(&x),sizeof(x)))v.push_back(x);return v;}
inline double strict_mul(double a,double b){volatile double z=a*b;return z;}
inline double strict_add(double a,double b){volatile double z=a+b;return z;}
inline double native_softplus(double x){return x>0?strict_add(x,std::log1p(std::exp(-x))):std::log1p(std::exp(x));}
inline double evaluate_raw(const Model& m,const double* row){double result=m.init;for(const auto& tr:m.trees){int i=0;while(tr.nodes[i].left!=-1){const auto& n=tr.nodes[i];volatile float x=static_cast<float>(row[n.feature]);i=static_cast<double>(x)<=n.threshold?n.left:n.right;}result=strict_add(result,strict_mul(m.learning_rate,tr.nodes[i].value));}return result;}
inline uint64_t bits(double x){return std::bit_cast<uint64_t>(x);}
