git clone https://github.com/suai-ms-2020/ms-task1-BatMaxim.git
Echo ^-1>ms-task1-BatMaxim/TASKID.txt
cd ms-task1-BatMaxim
DEL /s/q lab1.1.py
DEL /s/q lab1_2.m
DEL /s/q lab1_3.m
git add .
git commit -m "Return to the original version"
git push origin main
cd ..
RD /s/q "ms-task1-BatMaxim"
