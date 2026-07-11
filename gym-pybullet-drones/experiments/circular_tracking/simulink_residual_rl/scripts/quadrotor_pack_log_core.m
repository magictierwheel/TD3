function y = quadrotor_pack_log_core(t, x, ref, env, omegaCmd, ctrlDbg, plantDbg)
%QUADROTOR_PACK_LOG_CORE Pack fixed-width log vector for To Workspace.

y = zeros(66, 1);
y(1) = t;
y(2:20) = x(1:19);
y(21:30) = ref;
y(31:42) = env;
y(43:46) = omegaCmd;
y(47:56) = ctrlDbg;
y(57:66) = plantDbg;
end
