git clone https://github.com/suai-ms-2020/ms-task1-BatMaxim.git
Echo ^2>ms-task1-BatMaxim/TASKID.txt
Echo cd.>ms-task1-BatMaxim/lab1.1.py
Echo cd.>ms-task1-BatMaxim/lab1_2.m
Echo cd.>ms-task1-BatMaxim/lab1_3.m
cd ms-task1-BatMaxim
git add .
git commit -m "The work is done"
git push origin main
cd ..
RD /s/q "ms-task1-BatMaxim"
cd ..
pause
python main.py