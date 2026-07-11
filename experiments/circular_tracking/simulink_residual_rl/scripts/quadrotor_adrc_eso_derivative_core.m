function dxEso = quadrotor_adrc_eso_derivative_core(x, ref, p)
%QUADROTOR_ADRC_ESO_DERIVATIVE_CORE Extended-state observer dynamics.
%   ESO states are appended to the plant state:
%     x(20:22) = estimated position, x(23:25) = estimated velocity,
%     x(26:28) = estimated total acceleration disturbance.

dxEso = zeros(9, 1);

pos = x(1:3);
z1 = x(20:22);
z2 = x(23:25);
z3 = x(26:28);
u = quadrotor_adrc_outer_core(x, ref, p);

wH = max(p(98), 0.50);
wZ = max(p(99), 0.50);
w = [wH; wH; wZ];
beta1 = 3.0 * w;
beta2 = 3.0 * (w .* w);
beta3 = w .* w .* w;

e = z1 - pos;
dxEso(1:3) = z2 - beta1 .* e;
dxEso(4:6) = z3 + u - beta2 .* e;
dxEso(7:9) = -beta3 .* e;

for i = 1:9
    dxEso(i) = min(max(dxEso(i), -80.0), 80.0);
end
end
