#include <stdio.h>

int main() {
    int a = 15;
    int b = 4;
    int expr = 2 + 3 * 4 - (a / b);

    float x = 15.0;
    float y = 4.0;
    float precise = x / y + 1.25;

    expr += 5;
    expr++;

    printf("Int division a / b = %d\n", a / b);
    printf("Expression result = %d\n", expr);
    printf("Float result = %.2f\n", precise);
    return 0;
}
