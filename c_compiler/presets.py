from __future__ import annotations
from typing import Any


PRESETS: list[dict[str, Any]] = [
    {
        "id": "01_arithmetic",
        "title": "1. Арифметичні вирази",
        "filename": "01_arithmetic.c",
        "code": """#include <stdio.h>

int main() {
    int a = 15;
    int b = 4;
    int expr = 2 + 3 * 4 - (a / b);

    float x = 15.0;
    float y = 4.0;
    float precise = x / y + 1.25;

    expr += 5;
    expr++;

    printf("Int division a / b = %d\\n", a / b);
    printf("Expression result = %d\\n", expr);
    printf("Float result = %.2f\\n", precise);
    return 0;
}
""",
    },
    {
        "id": "02_dangling_else",
        "title": "2. Умовні оператори",
        "filename": "02_conditions.c",
        "code": """#include <stdio.h>

int classify_score(int score) {
    if (score >= 90)
        if (score == 100)
            return 5;
        else
            return 4;
    else if (score >= 75) {
        return 3;
    } else if (score >= 60) {
        return 2;
    } else {
        return 1;
    }
}

int main() {
    int s1 = 100;
    int s2 = 93;
    int s3 = 68;

    printf("Score %d -> level %d\\n", s1, classify_score(s1));
    printf("Score %d -> level %d\\n", s2, classify_score(s2));
    printf("Score %d -> level %d\\n", s3, classify_score(s3));
    return 0;
}
""",
    },
    {
        "id": "03_loops_arrays",
        "title": "3. Цикли та масиви",
        "filename": "03_loops_arrays.c",
        "code": """#include <stdio.h>

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
    printf("\\n");

    printf("Max element = %d\\n", max_val);
    printf("Sum of odd elements = %d\\n", sum_odd);
    return 0;
}
""",
    },
    {
        "id": "04_recursion",
        "title": "4. Рекурсія",
        "filename": "04_recursion.c",
        "code": """#include <stdio.h>

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
    printf("factorial(%d) = %d\\n", n, factorial(n));
    printf("Fibonacci sequence: ");
    for (int i = 0; i < 8; i++) {
        printf("%d ", fib(i));
    }
    printf("\\n");
    return 0;
}
""",
    },
    {
        "id": "05_bubble_sort",
        "title": "5. Сортування бульбашкою",
        "filename": "05_bubble_sort.c",
        "code": """#include <stdio.h>

void bubble_sort(int arr[], int n) {
    for (int i = 0; i < n - 1; i++) {
        bool swapped = false;
        for (int j = 0; j < n - i - 1; j++) {
            if (arr[j] > arr[j + 1]) {
                int temp = arr[j];
                arr[j] = arr[j + 1];
                arr[j + 1] = temp;
                swapped = true;
            }
        }
        if (!swapped) {
            break;
        }
    }
}

int main() {
    int data[7] = {64, 34, 25, 12, 22, 11, 90};
    int n = 7;

    bubble_sort(data, n);

    printf("Sorted array: ");
    for (int i = 0; i < n; i++) {
        printf("%d ", data[i]);
    }
    printf("\\n");
    return 0;
}
""",
    },
    {
        "id": "06_semantic_errors",
        "title": "6. Семантичні помилки",
        "filename": "06_error_demo.c",
        "code": """#include <stdio.h>

int add(int a, int b) {
    return a + b;
}

int main() {
    const int LIMIT = 100;
    LIMIT = 200;

    int res = add(5);
    int x = unknown_var + 1;
    break;
    return 0;
}
""",
    },
]
