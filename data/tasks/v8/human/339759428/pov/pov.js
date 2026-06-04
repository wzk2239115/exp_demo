function F0() {
        if (!new.target) { throw 'must be called with new'; }
        async function f2(a3, a4) {
            a3.constructor;
            const t3 = a3.constructor;
            const v7 = new t3(this, this, f2);
            const v8 = v7.constructor;
            try { new v8(); } catch (e) {}
            /{z}[\cA]a+b|ca{12z}/gmsd;
            (await this).ReferenceError();
            return v8;
        }
        f2(this);
    }
    new F0();
    // CRASH INFO
    // ==========
    // INSTANCE TAG: bac95ef1
    // TERMSIG: 6
    // STDERR:
    // [COV] edge counters initialized. Shared memory: shm_id_3450327_14 with 1309323 edges
    // 
    // 
    // #
    // # Fatal error in ../../src/deoptimizer/deoptimizer.cc, line 359
    // # Debug check failed: code.SafeEquals(topmost_) implies safe_to_deopt_.
    // #
    // #
    // #
    // #FailureMessage Object: 0x7f921b0c0060
    // ==== C stack trace ===============================
    // 
    //     ../v8/out/fuzzbuild/d8(___interceptor_backtrace+0x46) [0x5f5a036428a6]
    //     ../v8/out/fuzzbuild/d8(+0x1f61b02) [0x5f5a0393fb02]
    //     ../v8/out/fuzzbuild/d8(+0x1f5f18f) [0x5f5a0393d18f]
    //     ../v8/out/fuzzbuild/d8(+0x1f49477) [0x5f5a03927477]
    //     ../v8/out/fuzzbuild/d8(+0x1f4879f) [0x5f5a0392679f]
    //     ../v8/out/fuzzbuild/d8(+0x271c380) [0x5f5a040fa380]
    //     ../v8/out/fuzzbuild/d8(+0x271b5d2) [0x5f5a040f95d2]
    //     ../v8/out/fuzzbuild/d8(+0x271e14a) [0x5f5a040fc14a]
    //     ../v8/out/fuzzbuild/d8(+0x2867c83) [0x5f5a04245c83]
    //     ../v8/out/fuzzbuild/d8(+0x28b5bea) [0x5f5a04293bea]
    //     ../v8/out/fuzzbuild/d8(+0x423e239) [0x5f5a05c1c239]
    //     ../v8/out/fuzzbuild/d8(+0x423d969) [0x5f5a05c1b969]
    //     ../v8/out/fuzzbuild/d8(+0x7f82008) [0x5f5a09960008]
    // Received signal 6
    // STDOUT:
    // 
    // FUZZER ARGS: .build/x86_64-unknown-linux-gnu/debug/FuzzilliCli --profile=v8 ../v8/out/fuzzbuild/d8 --jobs=24 --engine=multi --logLevel=verbose --timeout=1200 --storagePath=../v8_fuzzing_results --resume --exportStatistics --statisticsExportInterval=5 --diagnostics --tag=3ea85f9c
    // TARGET ARGS: ../v8/out/fuzzbuild/d8 --expose-gc --omit-quit --allow-natives-syntax --fuzzing --jit-fuzzing --future --harmony --js-staging
    // CONTRIBUTORS: TypedArrayGenerator, IntegerGenerator, ExplorationMutator, ArrayGenerator
    // EXECUTION TIME: 171ms
    