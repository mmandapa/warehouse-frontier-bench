Implement a memory-bounded CTC loss and logit-gradient kernel. This is an ML training primitive: the loss marginalizes valid alignments between a sequence of frame predictions and an unaligned label sequence.

Work in `/app`. Read `/app/CONTRACT.md` for the complete mathematical definition, ABI, input domain, resource limits, tolerances, and scoring rule. `kernel.c` and `ctc_math.h` provide a correct dense baseline; the baseline cannot handle the large cases within the memory ceiling. You may change either file, use another implementation language, or change the build command, provided the submitted module satisfies the same contract.

Produce `/app/submission/kernel.wasm`. Only that file is transferred to an independent verifier. Compile the initial baseline with `bash build.sh`; run the public suite with:

```bash
python -m ctcbench.grade --module submission/kernel.wasm --fixtures public.npz
```

The private suite tests the same documented behavior and case families with different inputs. Success means every private case has the correct status, loss, and complete gradient, within the published memory and fuel limits. Do not modify the task's meaning, hardcode fixture answers, or rely on files, imports, or host services from inside the submitted module. Changes to local Python or public fixture files do not affect final grading.

You have 20 minutes, two CPU cores, and 4 GiB container memory. The module itself has a tighter linear-memory limit specified in the contract. Internet access is restricted to the model endpoint; all required tools, data, and baseline source are already installed.
