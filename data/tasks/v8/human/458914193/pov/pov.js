class C1 {}

const v1 = {
    n() {
        try { 
            this.n();
        } catch (e) {}

        class C2 {
            constructor() {
                class C3 extends C1 {
                    constructor() {}
                    a;
                    static {};
                    b;
                    static {
                        let x = 0;
                    }
                }
            }
        };

        new C2();
    }
};
let res = v1.n();
