#include <algorithm>
#include <bit>
#include <chrono>
#include <cfenv>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <fcntl.h>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <mutex>
#include <stdexcept>
#include <string>
#include <sys/mman.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <thread>
#include <unistd.h>
#include <vector>

static_assert(sizeof(double) == 8 && sizeof(float) == 4);
static_assert(std::endian::native == std::endian::little, "Gen7 frozen artifacts require little endian");

struct Node { int32_t left, right, feature; double threshold, value, weight; };
struct Tree { uint32_t max_depth; std::vector<Node> nodes; };
struct Model {
    uint32_t n_features;
    double learning_rate, init, raw_min, raw_max, loss_upper, reserved;
    std::vector<Tree> trees;
};

template <class T> T read_value(std::ifstream& f) {
    T value{};
    f.read(reinterpret_cast<char*>(&value), sizeof(T));
    if (!f) throw std::runtime_error("short model read");
    return value;
}

Model load_model(const std::string& path) {
    std::ifstream f(path, std::ios::binary);
    if (!f) throw std::runtime_error("model open");
    char magic[8];
    f.read(magic, 8);
    if (std::memcmp(magic, "SACGBM2\0", 8) != 0) throw std::runtime_error("model magic");
    const uint32_t version = read_value<uint32_t>(f);
    const uint32_t nf = read_value<uint32_t>(f);
    const uint32_t nt = read_value<uint32_t>(f);
    (void)read_value<uint32_t>(f);
    if (version != 2) throw std::runtime_error("model version");
    Model model{};
    model.n_features = nf;
    model.learning_rate = read_value<double>(f);
    model.init = read_value<double>(f);
    model.raw_min = read_value<double>(f);
    model.raw_max = read_value<double>(f);
    model.loss_upper = read_value<double>(f);
    model.reserved = read_value<double>(f);
    for (uint32_t t = 0; t < nt; ++t) {
        Tree tree{};
        const uint32_t count = read_value<uint32_t>(f);
        tree.max_depth = read_value<uint32_t>(f);
        tree.nodes.reserve(count);
        for (uint32_t i = 0; i < count; ++i) {
            Node node{};
            node.left = read_value<int32_t>(f);
            node.right = read_value<int32_t>(f);
            node.feature = read_value<int32_t>(f);
            node.threshold = read_value<double>(f);
            node.value = read_value<double>(f);
            node.weight = read_value<double>(f);
            tree.nodes.push_back(node);
        }
        model.trees.push_back(std::move(tree));
    }
    return model;
}

struct Mapping {
    int fd = -1;
    size_t bytes = 0;
    void* ptr = MAP_FAILED;
    ~Mapping() {
        if (ptr != MAP_FAILED) munmap(ptr, bytes);
        if (fd >= 0) close(fd);
    }
};

Mapping map_file(const std::string& path) {
    Mapping mapping;
    mapping.fd = open(path.c_str(), O_RDONLY);
    if (mapping.fd < 0) throw std::runtime_error("open " + path);
    struct stat st{};
    if (fstat(mapping.fd, &st)) throw std::runtime_error("stat " + path);
    mapping.bytes = static_cast<size_t>(st.st_size);
    mapping.ptr = mmap(nullptr, mapping.bytes, PROT_READ, MAP_PRIVATE, mapping.fd, 0);
    if (mapping.ptr == MAP_FAILED) throw std::runtime_error("mmap " + path);
    return mapping;
}

std::vector<uint32_t> load_indices(const std::string& path) {
    if (path.empty()) return {};
    std::ifstream f(path, std::ios::binary);
    if (!f) throw std::runtime_error("indices open");
    std::vector<uint32_t> values;
    uint32_t value;
    while (f.read(reinterpret_cast<char*>(&value), sizeof(value))) values.push_back(value);
    return values;
}

inline double strict_mul(double a, double b) { volatile double z = a * b; return z; }
inline double strict_add(double a, double b) { volatile double z = a + b; return z; }
inline double native_softplus(double x) {
    return x > 0.0 ? strict_add(x, std::log1p(std::exp(-x))) : std::log1p(std::exp(x));
}
inline double evaluate_raw(const Model& model, const double* row) {
    double result = model.init;
    for (const auto& tree : model.trees) {
        int node_index = 0;
        while (tree.nodes[node_index].left != -1) {
            const auto& node = tree.nodes[node_index];
            volatile float narrowed = static_cast<float>(row[node.feature]);
            node_index = static_cast<double>(narrowed) <= node.threshold ? node.left : node.right;
        }
        result = strict_add(result, strict_mul(model.learning_rate, tree.nodes[node_index].value));
    }
    return result;
}
inline uint64_t bits(double x) { return std::bit_cast<uint64_t>(x); }


int run_self_test() {
    const bool binary64 = sizeof(double) == 8 && std::numeric_limits<double>::is_iec559;
    const bool binary32 = sizeof(float) == 4 && std::numeric_limits<float>::is_iec559;
    const bool little = std::endian::native == std::endian::little;
    const bool round_nearest = std::fegetround() == FE_TONEAREST;
#ifdef __FAST_MATH__
    const bool fast_math_off = false;
#else
    const bool fast_math_off = true;
#endif
    const double positive_zero = 0.0;
    const double negative_zero = -0.0;
    const bool signed_zero = bits(positive_zero) != bits(negative_zero)
        && bits(negative_zero) == 0x8000000000000000ULL;
    const double sub = std::numeric_limits<double>::denorm_min();
    const bool subnormal = sub > 0.0 && std::fpclassify(sub) == FP_SUBNORMAL;
    const bool nonfinite_fail_closed = !std::isfinite(std::numeric_limits<double>::infinity())
        && !std::isfinite(std::numeric_limits<double>::quiet_NaN());
    const float f0 = 1.0f;
    const float f1 = std::nextafterf(f0, std::numeric_limits<float>::infinity());
    const double midpoint = (static_cast<double>(f0) + static_cast<double>(f1)) / 2.0;
    volatile double below_mid = std::nextafter(midpoint, -std::numeric_limits<double>::infinity());
    volatile double above_mid = std::nextafter(midpoint, std::numeric_limits<double>::infinity());
    const bool threshold_boundary = static_cast<float>(below_mid) == f0
        && static_cast<float>(above_mid) == f1;
    const double ordered = strict_add(strict_add(1.0e16, -1.0e16), 1.0);
    const double reordered = strict_add(1.0e16, strict_add(-1.0e16, 1.0));
    const bool ordered_accumulation = ordered == 1.0 && reordered == 0.0;
    volatile double a = 1.0000000000000002;
    volatile double b = 1.0000000000000002;
    volatile double c = -1.0000000000000004;
    const double separate = strict_add(strict_mul(a, b), c);
    const double fused = std::fma(a, b, c);
    const bool fma_separation = bits(separate) != bits(fused);
    const bool pass = binary64 && binary32 && little && round_nearest && fast_math_off
        && signed_zero && subnormal && nonfinite_fail_closed && threshold_boundary
        && ordered_accumulation && fma_separation;
    std::cout << "{"
        << "\"schema\":\"SAC_GEN7_CPP_SELFTEST_V2\","
        << "\"binary64\":" << (binary64 ? "true" : "false") << ","
        << "\"binary32\":" << (binary32 ? "true" : "false") << ","
        << "\"little_endian\":" << (little ? "true" : "false") << ","
        << "\"fe_tonearest\":" << (round_nearest ? "true" : "false") << ","
        << "\"fast_math_off\":" << (fast_math_off ? "true" : "false") << ","
        << "\"signed_zero\":" << (signed_zero ? "true" : "false") << ","
        << "\"subnormal\":" << (subnormal ? "true" : "false") << ","
        << "\"nonfinite_fail_closed\":" << (nonfinite_fail_closed ? "true" : "false") << ","
        << "\"threshold_nextafter_boundary\":" << (threshold_boundary ? "true" : "false") << ","
        << "\"ordered_accumulation\":" << (ordered_accumulation ? "true" : "false") << ","
        << "\"fma_result_distinct\":" << (fma_separation ? "true" : "false") << ","
        << "\"pass\":" << (pass ? "true" : "false") << "}\n";
    return pass ? 0 : 2;
}

int main(int argc, char** argv) {
    try {
        for (int i = 1; i < argc; ++i) {
            if (std::string(stringv[i]) == "--self-test") return run_self_test();
        }
        std::string model_path, x_path, y_path, loss_path, raw_path, indices_path, out_path;
        std::string truth_loss_path, truth_raw_path;
        uint64_t population = 0;
        double raw_tolerance = 0.0, loss_tolerance = 1.1e-10;
        int thread_count = 1;
        for (int i = 1; i < argc; ++i) {
            std::string arg = argv[i];
            auto need = [&]() -> std::string {
                if (i + 1 >= argc) throw std::runtime_error("missing argument value");
                return argv[++i];
            };
            if (arg == "--model") model_path = need();
            else if (arg == "--x") x_path = need();
            else if (arg == "--y") y_path = need();
            else if (arg == "--reported-loss") loss_path = need();
            else if (arg == "--reported-raw") raw_path = need();
            else if (arg == "--indices") indices_path = need();
            else if (arg == "--out") out_path = need();
            else if (arg == "--truth-loss-out") truth_loss_path = need();
            else if (arg == "--truth-raw-out") truth_raw_path = need();
            else if (arg == "--n") population = std::stoull(need());
            else if (arg == "--raw-tol") raw_tolerance = std::stod(need());
            else if (arg == "--loss-tol") loss_tolerance = std::stod(need());
            else if (arg == "--threads") thread_count = std::max(1, std::stoi(need()));
            else throw std::runtime_error("unknown argument " + arg);
        }
        if (model_path.empty() || x_path.empty() || y_path.empty() || loss_path.empty()
            || raw_path.empty() || out_path.empty() || population == 0) {
            throw std::runtime_error("required argument missing");
        }

        const auto wall_start = std::chrono::steady_clock::now();
        const auto cpu_start = cpu_ns();
        const Model model = load_model(model_path);
        Mapping x_map = map_file(x_path), y_map = map_file(y_path);
        Mapping loss_map = map_file(loss_path), raw_map = map_file(raw_path);
        const std::vector<uint32_t> indices = load_indices(indices_path);
        if (x_map.bytes != population * model.n_features * sizeof(double)
            || y_map.bytes != population * sizeof(double)
            || loss_map.bytes != population * sizeof(double)
            || raw_map.bytes != population * sizeof(double)) {
            throw std::runtime_error("artifact size mismatch");
        }
        const auto* x = static_cast<const double*>(x_map.ptr);
        const auto* y = static_cast<const double*>(y_map.ptr);
        const auto* reported_loss = static_cast<const double*>(loss_map.ptr);
        const auto* reported_raw = static_cast<const double*>(raw_map.ptr);
        const uint64_t count = indices.empty() ? population : indices.size();
        thread_count = std::min<int>(thread_count, std::max<uint64_t>(1, count));

        std::vector<long double> sums(thread_count, 0.0L);
        std::vector<uint64_t> loss_mismatches(thread_count, 0), raw_mismatches(thread_count, 0);
        std::vector<uint64_t> adverse_mismatches(thread_count, 0), bound_violations(thread_count, 0);
        std::vector<double> max_raw_error(thread_count, 0.0), max_loss_error(thread_count, 0.0);
        std::vector<double> truth_loss(truth_loss_path.empty() ? 0 : count);
        std::vector<double> truth_raw(truth_raw_path.empty() ? 0 : count);
        std::vector<std::thread> workers;
        std::exception_ptr worker_error;
        std::mutex error_mutex;

        auto work = [&](int worker) {
            try {
                const uint64_t begin = count * worker / thread_count;
                const uint64_t end = count * (worker + 1) / thread_count;
                long double sum = 0.0L;
                uint64_t lm = 0, rm = 0, am = 0, bv = 0;
                double mre = 0.0, mle = 0.0;
                for (uint64_t position = begin; position < end; ++position) {
                    const uint64_t unit = indices.empty() ? position : indices[position];
                    if (unit >= population) throw std::runtime_error("index out of range");
                    const double raw = evaluate_raw(model, x + unit * model.n_features);
                    const double loss = strict_add(native_softplus(raw), -(y[unit] > 0.0 ? raw : 0.0));
                    if (!std::isfinite(raw) || !std::isfinite(loss)) throw std::runtime_error("nonfinite truth");
                    const double raw_error = std::abs(raw - reported_raw[unit]);
                    const double loss_error = std::abs(loss - reported_loss[unit]);
                    const bool raw_bad = raw_tolerance == 0.0
                        ? bits(raw) != bits(reported_raw[unit])
                        : raw_error > raw_tolerance;
                    if (raw_bad) ++rm;
                    if (loss_error > loss_tolerance) ++lm;
                    if (loss - reported_loss[unit] > loss_tolerance) ++am;
                    if (raw < model.raw_min || raw > model.raw_max || loss > model.loss_upper) ++bv;
                    mre = std::max(mre, raw_error);
                    mle = std::max(mle, loss_error);
                    sum += loss;
                    if (!truth_loss_path.empty()) truth_loss[position] = loss;
                    if (!truth_raw_path.empty()) truth_raw[position] = raw;
                }
                sums[worker] = sum;
                loss_mismatches[worker] = lm;
                raw_mismatches[worker] = rm;
                adverse_mismatches[worker] = am;
                bound_violations[worker] = bv;
                max_raw_error[worker] = mre;
                max_loss_error[worker] = mle;
            } catch (...) {
                std::lock_guard<std::mutex> guard(error_mutex);
                if (!worker_error) worker_error = std::current_exception();
            }
        };

        for (int worker = 0; worker < thread_count; ++worker) workers.emplace_back(work, worker);
        for (auto& worker : workers) worker.join();
        if (worker_error) std::rethrow_exception(worker_error);

        long double total = 0.0L;
        uint64_t lm = 0, rm = 0, am = 0, bv = 0;
        double mre = 0.0, mle = 0.0;
        for (int worker = 0; worker < thread_count; ++worker) {
            total += sums[worker];
            lm += loss_mismatches[worker];
            rm += raw_mismatches[worker];
            am += adverse_mismatches[worker];
            bv += bound_violations[worker];
            mre = std::max(mre, max_raw_error[worker]);
            mle = std::max(mle, max_loss_error[worker]);
        }
        if (!truth_loss_path.empty()) {
            std::ofstream f(truth_loss_path, std::ios::binary);
            f.write(reinterpret_cast<const char*>(truth_loss.data()), truth_loss.size() * sizeof(double));
            if (!f) throw std::runtime_error("truth loss write");
        }
        if (!truth_raw_path.empty()) {
            std::ofstream f(truth_raw_path, std::ios::binary);
            f.write(reinterpret_cast<const char*>(truth_raw.data()), truth_raw.size() * sizeof(double));
            if (!f) throw std::runtime_error("truth raw write");
        }

        const auto cpu_end = cpu_ns();
        const auto wall_end = std::chrono::steady_clock::now();
        rusage usage{};
        getrusage(RUSAGE_SELF, &usage);
        const double mean = static_cast<double>(total / count);
        std::ofstream output(out_path);
        output << std::setprecision(17)
            << "{\"schema\":\"SAC_GEN7_GB_ORACLE_V2\","
            << "\"count\":" << count << ","
            << "\"population\":" << population << ","
            << "\"raw_mismatches\":" << rm << ","
            << "\"loss_interval_mismatches\":" << lm << ","
            << "\"adverse_loss_mismatches\":" << am << ","
            << "\"bound_violations\":" << bv << ","
            << "\"max_abs_raw_error\":" << mre << ","
            << "\"max_abs_loss_error\":" << mle << ","
            << "\"raw_tolerance\":" << raw_tolerance << ","
            << "\"loss_tolerance\":" << loss_tolerance << ","
            << "\"mean_native_loss\":" << mean << ","
            << "\"native_decision\":" << (mean < 0.5 ? "true" : "false") << ","
            << "\"wall_ns\":" << std::chrono::duration_cast<std::chrono::nanoseconds>(wall_end - wall_start).count() << ","
            << "\"cpu_ns\":" << (cpu_end - cpu_start) << ","
            << "\"peak_rss_native_units\":" << usage.ru_maxrss << ","
            << "\"threads\":" << thread_count << ","
            << "\"float32_tree_semantics\":true,"
            << "\"strict_binary64_accumulation\":true,"
            << "\"probability_clipping\":\"NONE\"}"
            << "\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << "\n";
        return 2;
    }
}
