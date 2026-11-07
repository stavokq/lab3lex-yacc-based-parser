#include <stdio.h>

int main() {
    int nums[6] = {12, 7, 25, 4, 18, 9};
    int sum_odd = 0;
    int max_val = nums[0];

    for (int i = 0; i < 6; i++) {
        if (nums[i] > max_val) {
            max_val = nums[i];
        }
        if (nums[i] % 2 == 0) {
            continue;
        }
        sum_odd += nums[i];
    }

    int countdown = 3;
    do {
        printf("Tick %d... ", countdown);
        countdown--;
    } while (countdown > 0);
    printf("\n");

    printf("Max element = %d\n", max_val);
    printf("Sum of odd elements = %d\n", sum_odd);
    return 0;
}
