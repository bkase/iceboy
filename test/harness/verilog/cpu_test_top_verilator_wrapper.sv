module cpu_test_top_verilator_wrapper (
    input clk_i,
    input rst_i,
    input [44:0] stimulus_i,
    input [7:0] bus_read_data_i,
    input [4:0] irq_pending_i,
    output [140:0] output__
);
    \iceboy::sim::cpu_test_top::cpu_test_top  impl (
        .clk_i(clk_i),
        .rst_i(rst_i),
        .stimulus_i(stimulus_i),
        .bus_read_data_i(bus_read_data_i),
        .irq_pending_i(irq_pending_i),
        .output__(output__)
    );
endmodule
