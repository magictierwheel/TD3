# Formula Sources

## (1) 状态和目标信号

```latex
\mathbf{x}=\begin{bmatrix}\mathbf{r}\\ \mathbf{v}\\ \boldsymbol{\eta}\\ \boldsymbol{\omega}\\ \mathbf{e}_I\\ \boldsymbol{\Omega}\end{bmatrix},\qquad \mathbf{q}_{ref}=\begin{bmatrix}\mathbf{r}_{ref}\\ \mathbf{v}_{ref}\\ \mathbf{a}_{ref}\\ \psi_{ref}\end{bmatrix}
```

## (2) 匀速圆周参考轨迹

```latex
\mathbf{r}_{ref}(t)=\begin{bmatrix}R\cos(\omega_c t)\\ R\sin(\omega_c t)\\ h\end{bmatrix},\quad \mathbf{v}_{ref}(t)=\begin{bmatrix}-R\omega_c\sin(\omega_c t)\\ R\omega_c\cos(\omega_c t)\\0\end{bmatrix},\quad \mathbf{a}_{ref}(t)=\begin{bmatrix}-R\omega_c^2\cos(\omega_c t)\\-R\omega_c^2\sin(\omega_c t)\\0\end{bmatrix}
```

## (3) 位置误差和速度误差

```latex
\mathbf{e}_r=\mathbf{r}_{ref}-\mathbf{r},\qquad \mathbf{e}_v=\mathbf{v}_{ref}-\mathbf{v}
```

## (4) 原 PID 外环

```latex
\mathbf{a}_{PID}=\mathbf{a}_{ref}+K_p\mathbf{e}_r+K_d\mathbf{e}_v+K_i\mathbf{e}_I
```

## (5) 环境和旋翼效率

```latex
\rho=\frac{P}{R_{air}(T_0+\Delta T)},\qquad f_T=\max\left(0.25,\frac{\rho}{\rho_0}\eta_T\right),\qquad f_Q=\max\left(0.25,\frac{\rho}{\rho_0}\eta_Q\right)
```

## (6) 风阻和热上升扰动

```latex
\mathbf{a}_{drag}=-\frac{1}{2m}\rho C_DA\,\|\mathbf{v}-\mathbf{w}\|(\mathbf{v}-\mathbf{w}),\qquad \mathbf{a}_{thermal}=\begin{bmatrix}0\\0\\a_{th}\end{bmatrix}
```

## (7) PID 扰动前馈补偿

```latex
\mathbf{a}_{cmd}=\mathbf{a}_{PID}-\mathbf{a}_{drag}-\mathbf{a}_{thermal},\qquad T_{cmd}\leftarrow \frac{T_{cmd}}{f_T},\qquad \boldsymbol{\tau}_{xy}\leftarrow \frac{\boldsymbol{\tau}_{xy}}{f_T},\quad \tau_z\leftarrow \frac{\tau_z}{f_Q}
```

## (8) MPC 的预测模型和优化目标

```latex
\begin{aligned}\mathbf{s}_{k+1}&=\begin{bmatrix}1&T_s\\0&1\end{bmatrix}\mathbf{s}_k+\begin{bmatrix}\frac{1}{2}T_s^2\\T_s\end{bmatrix}u_k,\\ \min_{\{u_k\}}\ J&=\sum_{k=1}^{N}\left(q_r\|r_k-r_{ref,k}\|^2+q_v\|v_k-v_{ref,k}\|^2+r_u\|u_k\|^2\right)\end{aligned}
```

## (9) ADRC 的扩张状态观测器

```latex
\begin{aligned}\dot{\mathbf{z}}_1&=\mathbf{z}_2-\beta_1(\mathbf{z}_1-\mathbf{r}),\\ \dot{\mathbf{z}}_2&=\mathbf{z}_3+\mathbf{u}-\beta_2(\mathbf{z}_1-\mathbf{r}),\\ \dot{\mathbf{z}}_3&=-\beta_3(\mathbf{z}_1-\mathbf{r})\end{aligned}
```

## (10) ADRC 外环控制律

```latex
\mathbf{u}_{ADRC}=\mathbf{a}_{ref}+K_p(\mathbf{r}_{ref}-\mathbf{r})+K_d(\mathbf{v}_{ref}-\mathbf{v})-\Gamma\mathbf{z}_3
```

## (11) 强化学习残差策略

```latex
\mathbf{a}_{cmd}=\mathbf{a}_{PID}+\Delta\mathbf{a}_{RL},\qquad [\Delta\mathbf{a}_{RL},s_T,s_{\tau}]=\pi_{\theta}(\mathbf{x},\mathbf{q}_{ref},\mathbf{e}_{env})
```

## (12) 加速度到目标姿态

```latex
\phi_{des}=\frac{a_x\sin\psi_{ref}-a_y\cos\psi_{ref}}{g},\qquad \theta_{des}=\frac{a_x\cos\psi_{ref}+a_y\sin\psi_{ref}}{g}
```

## (13) 总推力命令

```latex
T_{cmd}=\frac{m(g+a_z)}{\cos\phi\cos\theta}
```

## (14) 四旋翼电机分配

```latex
\begin{bmatrix}T\\\tau_x\\\tau_y\\\tau_z\end{bmatrix}=\begin{bmatrix}k_f&k_f&k_f&k_f\\0&lk_f&0&-lk_f\\-lk_f&0&lk_f&0\\-k_q&k_q&-k_q&k_q\end{bmatrix}\begin{bmatrix}\Omega_1^2\\\Omega_2^2\\\Omega_3^2\\\Omega_4^2\end{bmatrix}
```

## (15) 动力学闭环

```latex
\dot{\mathbf{r}}=\mathbf{v},\qquad \dot{\mathbf{v}}=\frac{R_{BW}\begin{bmatrix}0\\0\\T\end{bmatrix}}{m}-\begin{bmatrix}0\\0\\g\end{bmatrix}+\mathbf{a}_{drag}+\mathbf{a}_{thermal}
```
