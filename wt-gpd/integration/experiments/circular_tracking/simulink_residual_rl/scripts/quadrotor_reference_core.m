function ref = quadrotor_reference_core(t, scenarioId, p)
%QUADROTOR_REFERENCE_CORE Fixed-size reference generator for Simulink blocks.
%   ref = [r_ref(3); v_ref(3); a_ref(3); yaw_ref].

ref = zeros(10, 1);

if scenarioId < 1.5
    ref(1:3) = [0; 0; p(70)];
elseif scenarioId < 2.5
    radius = p(71);
    rate = p(72);
    alt = p(73);
    wt = rate * t;
    c = cos(wt);
    s = sin(wt);
    ref(1:3) = [radius * c; radius * s; alt];
    ref(4:6) = [-radius * rate * s; radius * rate * c; 0];
    ref(7:9) = [-radius * rate * rate * c; -radius * rate * rate * s; 0];
else
    T = p(74);
    startPos = p(75:77);
    goalPos = p(78:80);
    delta = goalPos - startPos;
    if t <= 0
        tau = 0;
    elseif t >= T
        tau = 1;
    else
        tau = t / T;
    end
    s = 10*tau^3 - 15*tau^4 + 6*tau^5;
    if t > 0 && t < T
        sd = (30*tau^2 - 60*tau^3 + 30*tau^4) / T;
        sdd = (60*tau - 180*tau^2 + 120*tau^3) / (T*T);
    else
        sd = 0;
        sdd = 0;
    end
    ref(1:3) = startPos + s * delta;
    ref(4:6) = sd * delta;
    ref(7:9) = sdd * delta;
end

ref(10) = 0;
end
