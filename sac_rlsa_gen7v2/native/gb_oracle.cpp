#include "oracle_model.hpp"
#include "oracle_selftest.hpp"
#include <chrono>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <mutex>
#include <sys/resource.h>
#include <thread>

inline uint64_t cpu_ns(){rusage u{};getrusage(RUSAGE_SELF,&u);return uint64_t(u.ru_utime.tv_sec+u.ru_stime.tv_sec)*1000000000ULL+uint64_t(u.ru_utime.tv_usec+u.ru_stime.tv_usec)*1000ULL;}

int main(int argc,char** argv){
 try{
  for(int i=1;i<argc;++i)if(std::string(argv[i])=="--self-test")return run_self_test();
  std::string model_path,x_path,y_path,loss_path,raw_path,indices_path,out_path,truth_loss_path,truth_raw_path;
  uint64_t population=0;double raw_tol=0.0,loss_tol=1.1e-10;int threads=1;
  for(int i=1;i<argc;++i){std::string arg=argv[i];auto need=[&](){if(i+1>=argc)throw std::runtime_error("missing argument value");return std::string(argv[++i]);};
   if(arg=="--model")model_path=need();else if(arg=="--x")x_path=need();else if(arg=="--y")y_path=need();else if(arg=="--reported-loss")loss_path=need();else if(arg=="--reported-raw")raw_path=need();else if(arg=="--indices")indices_path=need();else if(arg=="--out")out_path=need();else if(arg=="--truth-loss-out")truth_loss_path=need();else if(arg=="--truth-raw-out")truth_raw_path=need();else if(arg=="--n")population=std::stoull(need());else if(arg=="--raw-tol")raw_tol=std::stod(need());else if(arg=="--loss-tol")loss_tol=std::stod(need());else if(arg=="--threads")threads=std::max(1,std::stoi(need()));else throw std::runtime_error("unknown argument "+arg);}
  if(model_path.empty()||x_path.empty()||y_path.empty()||loss_path.empty()||raw_path.empty()||out_path.empty()||!population)throw std::runtime_error("required argument missing");
  const auto wall0=std::chrono::steady_clock::now();const uint64_t cpu0=cpu_ns();
  const Model model=load_model(model_path);Mapping xm=map_file(x_path),ym=map_file(y_path),lm=map_file(loss_path),rm=map_file(raw_path);auto indices=load_indices(indices_path);
  if(xm.bytes!=population*model.n_features*sizeof(double)||ym.bytes!=population*sizeof(double)||lm.bytes!=population*sizeof(double)||rm.bytes!=population*sizeof(double))throw std::runtime_error("artifact size mismatch");
  const double* x=static_cast<const double*>(xm.ptr);const double* y=static_cast<const double*>(ym.ptr);const double* reported_loss=static_cast<const double*>(lm.ptr);const double* reported_raw=static_cast<const double*>(rm.ptr);
  const uint64_t count=indices.empty()?population:indices.size();threads=std::min<int>(threads,std::max<uint64_t>(1,count));
  std::vector<long double>sums(threads,0.0L);std::vector<uint64_t>loss_bad(threads),raw_bad(threads),adverse(threads),bounds(threads);std::vector<double>max_re(threads),max_le(threads);std::vector<double>truth_loss(truth_loss_path.empty()?0:count),truth_raw(truth_raw_path.empty()?0:count);std::vector<std::thread>workers;std::exception_ptr worker_error;std::mutex error_mutex;
  auto work=[&](int w){try{uint64_t begin=count*w/threads,end=count*(w+1)/threads;long double sum=0;uint64_t lb=0,rb=0,ad=0,bv=0;double mre=0,mle=0;
    for(uint64_t pos=begin;pos<end;++pos){uint64_t unit=indices.empty()?pos:indices[pos];if(unit>=population)throw std::runtime_error("index out of range");double raw=evaluate_raw(model,x+unit*model.n_features);double loss=strict_add(native_softplus(raw),-(y[unit]>0?raw:0.0));if(!std::isfinite(raw)||!std::isfinite(loss))throw std::runtime_error("nonfinite truth");double re=std::abs(raw-reported_raw[unit]),le=std::abs(loss-reported_loss[unit]);bool rbad=raw_tol==0.0?bits(raw)!=bits(reported_raw[unit]):re>raw_tol;if(rbad)++rb;if(le>loss_tol)++lb;if(loss-reported_loss[unit]>loss_tol)++ad;if(raw<model.raw_min||raw>model.raw_max||loss>model.loss_upper)++bv;mre=std::max(mre,re);mle=std::max(mle,le);sum+=loss;if(!truth_loss_path.empty())truth_loss[pos]=loss;if(!truth_raw_path.empty())truth_raw[pos]=raw;}
    sums[w]=sum;loss_bad[w]=lb;raw_bad[w]=rb;adverse[w]=ad;bounds[w]=bv;max_re[w]=mre;max_le[w]=mle;
   }catch(...){std::lock_guard<std::mutex>g(error_mutex);if(!worker_error)worker_error=std::current_exception();}};
  for(int w=0;w<threads;++w)workers.emplace_back(work,w);for(auto& t:workers)t.join();if(worker_error)std::rethrow_exception(worker_error);
  long double total=0;uint64_t lb=0,rb=0,ad=0,bv=0;double mre=0,mle=0;for(int w=0;w<threads;++w){total+=sums[w];lb+=loss_bad[w];rb+=raw_bad[w];ad+=adverse[w];bv+=bounds[w];mre=std::max(mre,max_re[w]);mle=std::max(mle,max_le[w]);}
  if(!truth_loss_path.empty()){std::ofstream f(truth_loss_path,std::ios::binary);f.write(reinterpret_cast<const char*>(truth_loss.data()),truth_loss.size()*sizeof(double));if(!f)throw std::runtime_error("truth loss write");}
  if(!truth_raw_path.empty()){std::ofstream f(truth_raw_path,std::ios::binary);f.write(reinterpret_cast<const char*>(truth_raw.data()),truth_raw.size()*sizeof(double));if(!f)throw std::runtime_error("truth raw write");}
  const uint64_t cpu1=cpu_ns();const auto wall1=std::chrono::steady_clock::now();rusage usage{};getrusage(RUSAGE_SELF,&usage);double mean=static_cast<double>(total/count);
  std::ofstream out(out_path);out<<std::setprecision(17)<<"{\"schema\":\"SAC_GEN7_GB_ORACLE_V2\",\"count\":"<<count<<",\"population\":"<<population<<",\"raw_mismatches\":"<<rb<<",\"loss_interval_mismatches\":"<<lb<<",\"adverse_loss_mismatches\":"<<ad<<",\"bound_violations\":"<<bv<<",\"max_abs_raw_error\":"<<mre<<",\"max_abs_loss_error\":"<<mle<<",\"raw_tolerance\":"<<raw_tol<<",\"loss_tolerance\":"<<loss_tol<<",\"mean_native_loss\":"<<mean<<",\"native_decision\":"<<(mean<0.5?"true":"false")<<",\"wall_ns\":"<<std::chrono::duration_cast<std::chrono::nanoseconds>(wall1-wall0).count()<<",\"cpu_ns\":"<<(cpu1-cpu0)<<",\"peak_rss_native_units\":"<<usage.ru_maxrss<<",\"threads\":"<<threads<<",\"float32_tree_semantics\":true,\"strict_binary64_accumulation\":true,\"probability_clipping\":\"NONE\"}\n";if(!out)throw std::runtime_error("output write");
  return 0;
 }catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 2;}
}
