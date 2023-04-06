import math
list = [[1,2,3], [2,3,4], [3,4,5], [1,3,5]]

for i in range(len(list)):
    for j in range(len(list)):
        if i != j:
            a = math.dist(list[i], list[j])
            print("{} vs {}".format(i,j))
            print(a)