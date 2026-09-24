# Repaired oracle source

`gb_oracle.cpp.b64` is the byte-exact base64 encoding of the frozen C++20 source whose **decoded** SHA-256 is:

```text
8c743aa15685f18bf70830c78a3ce61580734d7144ac0039cd5681814bf2e46a
```

`tools/compile_oracle.sh` decodes the source to an external temporary file, verifies that digest, and only then compiles it with `-O3 -std=c++20 -pthread`.

The frozen execution semantics are:

```text
split:        float32(x_feature) <= stored binary64 threshold
accumulation: binary64 init + learning_rate * leaf value
loss:         logaddexp(0, raw) - y01 * raw
clipping:     none
```
