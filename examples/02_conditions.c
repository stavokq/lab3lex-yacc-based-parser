#include <stdio.h>

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

    printf("Score %d -> level %d\n", s1, classify_score(s1));
    printf("Score %d -> level %d\n", s2, classify_score(s2));
    printf("Score %d -> level %d\n", s3, classify_score(s3));
    return 0;
}
