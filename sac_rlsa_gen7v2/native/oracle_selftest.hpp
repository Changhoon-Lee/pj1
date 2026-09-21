#pragma once
#include "oracle_model.hpp"
#include <cfenv>
#include <cmath>
#include <iostream>

inline int run_self_test(){
 bool binary64=sizeof(double)==8&&std::numeric_limits<double>::is_iec559;
 bool binary32=sizeof(float)==4&&std::numeric_limits<float>::is_iec559;
 bool little=std::endian::native==std::endian::little;
 bool nearest=std::fegetround()==FE_TONEAREST;
#ifdef __FAST_MATH__
 bool fast_off=false;
#else
 bool fast_off=true;
#endif
 bool signed_zero=bits(0.0)!=bits(-0.0)&&bits(-0.0)==0x8000000000000000ULL;
 double sub=std::numeric_limits<double>::denorm_min();bool subnormal=sub>0&&std::fpclassify(sub)==FP_SUBNORMAL;
 bool nonfinite=!std::isfinite(std::numeric_limits<double>::infinity())&&!std::isfinite(std::numeric_limits<double>::quiet_NaN());
 float f0=1.0f,f1=std::nextafterf(f0,std::numeric_limits<float>::infinity());double mid=(double(f0)+double(f1))/2.0;
 volatile double below=std::nextafter(mid,-std::numeric_limits<double>::infinity()),above=std::nextafter(mid,std::numeric_limits<double>::infinity());
 bool threshold=static_cast<float>(below)==f0&&static_cast<float>(above)==f1;
 double ordered=strict_add(strict_add(1e16,-1e16),1.0),reordered=strict_add(1e16,strict_add(-1e16,1.0));bool order=ordered==1.0&&reordered==0.0;
 volatile double a=1.0000000000000002,b=1.0000000000000002,c=-1.0000000000000004;double separate=strict_add(strict_mul(a,b),c),fused=std::fma(a,b,c);bool fma_distinct=bits(separate)!=bits(fused);
 bool pass=binary64&&binary32&&little&&nearest&&fast_off&&signed_zero&&subnormal&&nonfinite&&threshold&&order&&fma_distinct;
 std::cout<<"{\"schema\":\"SAC_GEN7_CPP_SELFTEST_V2\",\"binary64\":"<<(binary64?"true":"false")<<",\"binary32\":"<<(binary32?"true":"false")<<",\"little_endian\":"<<(little?"true":"false")<<",\"fe_tonearest\":"<<(nearest?"true":"false")<<",\"fast_math_off\":"<<(fast_off?"true":"false")<<",\"signed_zero\":"<<(signed_zero?"true":"false")<<",\"subnormal\":"<<(subnormal?"true":"false")<<",\"nonfinite_fail_closed\":"<<(nonfinite?"true":"false")<<",\"threshold_nextafter_boundary\":"<<(threshold?"true":"false")<<",\"ordered_accumulation\":"<<(order?"true":"false")<<",\"fma_result_distinct\":"<<(fma_distinct?"true":"false")<<",\"pass\":"<<(pass?"true":"false")<<"}\n";
 return pass?0:2;
}
