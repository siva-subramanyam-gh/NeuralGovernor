#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <time.h>
#include <string.h>

#define MAX_STATES 100
#define EPISODES 40000
#define STEPS 300

double q_table[MAX_STATES][4] = {0.0};
int known_states = 0;
int state_tracker[MAX_STATES] = {0};

double gear_heating[] = {0.0, 0.03, 0.07, 0.14, 0.25};
int mhz_map[] = {0, 800, 1500, 2200, 2800};
double cooling_factor = 0.008;

double get_rand(double min, double max) {
    return min + ((double)rand() / RAND_MAX) * (max - min);
}

int get_state(double *history, int h_len, double temp) {
    if (h_len < 5) return (int)round(temp);
    
    double old_avg = (history[0] + history[1] + history[2]) / 3.0;
    double new_avg = (history[h_len-3] + history[h_len-2] + history[h_len-1]) / 3.0;
    
    double delta = (new_avg - old_avg) * 6.0;
    double proj = fmax(-1.0, fmin(2.0, delta));
    
    int state = (int)round(temp + proj);
    if (state < 0) state = 0;
    if (state >= MAX_STATES) state = MAX_STATES - 1;
    
    return state;
}

int get_best_action(int state) {
    int best_a = 0;
    double best_v = q_table[state][0];
    for (int i = 1; i < 4; i++) {
        if (q_table[state][i] > best_v) {
            best_v = q_table[state][i];
            best_a = i;
        }
    }
    return best_a;
}

void get_load_profile(double *profile) {
    int type = rand() % 4;
    for (int i = 0; i < STEPS; i++) {
        if (type == 0) profile[i] = get_rand(0.8, 1.0);
        else if (type == 1) profile[i] = get_rand(0.4, 0.6);
        else if (type == 2) profile[i] = ((i / 30) % 2 == 0) ? 1.0 : 0.2;
        else profile[i] = get_rand(0.1, 1.0);
    }
}

int main() {
    srand(time(NULL));
    
    double lr = 0.1;
    double df = 0.95;
    double eps = 1.0;
    double eps_decay = 0.9995;
    double min_eps = 0.01;
    
    printf("--- Training(%d Episodes) ---\n", EPISODES);
    
    double profile[STEPS];
    double history[10];
    
    for (int ep = 0; ep < EPISODES; ep++) {
        get_load_profile(profile);
        double temp = 25.0;
        int h_len = 0;
        int curr_gear = 4;
        int cooldown = 0;
        
        for (int i = 0; i < STEPS; i++) {
            double load = profile[i];
            
            if (h_len < 10) {
                history[h_len++] = temp;
            } else {
                memmove(history, history + 1, 9 * sizeof(double));
                history[9] = temp;
            }
            
            int state = get_state(history, h_len, temp);
            
            if (state_tracker[state] == 0) {
                state_tracker[state] = 1;
                known_states++;
            }
            
            int target_gear;
            if (((double)rand() / RAND_MAX) < eps) {
                target_gear = (rand() % 4) + 1;
            } else {
                target_gear = get_best_action(state) + 1;
            }
            
            int new_gear;
            int shifted = 0;
            
            if (temp > 45.0 || (target_gear != curr_gear && cooldown <= 0)) {
                new_gear = target_gear;
                cooldown = 10;
                shifted = 1;
            } else {
                new_gear = curr_gear;
                cooldown -= 1;
                shifted = 0;
            }
            
            double heat_in = gear_heating[new_gear] * load;
            double heat_out = cooling_factor * (temp - 25.0);
            double next_temp = temp + heat_in - heat_out + get_rand(-0.05, 0.05);
            
            int freq = mhz_map[new_gear];
            double work = (freq / 1000.0) * load;
            if (shifted) work *= 0.85;
            
            double reward = work * 20.0;
            
            if (next_temp >= 45.0) {
                reward -= 200.0;
            } else if (next_temp >= 43.5) {
                if (new_gear == 4) reward -= 60.0;
                if (new_gear == 3) reward -= 10.0;
            } else if (next_temp < 40.0) {
                if (new_gear < 4) reward -= 40.0;
            }
            
            if (load > 0.8 && freq < 2000) reward -= 50.0;
            if (shifted) reward -= 15.0;
            
            temp = next_temp;
            int next_state = get_state(history, h_len, temp);
            
            double old_val = q_table[state][target_gear - 1];
            double next_max = q_table[next_state][get_best_action(next_state)];
            
            q_table[state][target_gear - 1] = old_val + lr * (reward + df * next_max - old_val);
            curr_gear = new_gear;
        }
        
        if (eps > min_eps) eps *= eps_decay;
        
        if ((ep + 1) % 1500 == 0) {
            printf(" Episode %d/%d | Epsilon: %.3f | States: %d\n", ep + 1, EPISODES, eps, known_states);
        }
    }

    FILE *f = fopen("q_table_matrix.h", "w");
    if (f) {
        fprintf(f, "#ifndef Q_TABLE_MATRIX\n#define Q_TABLE_MATRIX_H\n\n");
        fprintf(f, "static const int q_table[%d][4] = {\n", MAX_STATES);
        for (int i = 0; i < MAX_STATES; i++) {
            fprintf(f, "    {%d, %d, %d, %d}",
                    (int)(q_table[i][0] * 10000.0), (int)(q_table[i][1] * 10000.0),
                    (int)(q_table[i][2] * 10000.0), (int)(q_table[i][3] * 10000.0));
            if (i < MAX_STATES - 1) fprintf(f, ",\n");
            else fprintf(f, "\n");
        }
        fprintf(f, "};\n\n#endif\n");
        fclose(f);
        printf("\n [SUCCESS] q_table_matrix.h generated for Kernel.\n");
    }
    
    return 0;
}
