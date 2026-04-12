module hardware_soc_core_verilator_wrapper (
    input clk_i,
    input rst_i,
    output [39:0] output__
);
    hardware_soc_core_verilator_top impl (
        .clk_i(clk_i),
        .rst_i(rst_i),
        .status_o(output__)
    );
endmodule
