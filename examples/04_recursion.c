#include <stdio.h>

int factorial(int n) {
    if (n <= 1) {
        return 1;
    }
    return n * factorial(n - 1);
}

int fib(int n) {
    if (n <= 1) {
        return n;
    }
    return fib(n - 1) + fib(n - 2);
}

int main() {
    int n = 6;
    printf("factorial(%d) = %d\n", n, factorial(n));
    printf("Fibonacci sequence: ");
    for (int i = 0; i < 8; i++) {
        printf("%d ", fib(i));
    }
    printf("\n");
    return 0;
}
