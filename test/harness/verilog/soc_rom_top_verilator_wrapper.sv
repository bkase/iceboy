module soc_rom_top_verilator_wrapper (
    input clk_i,
    input rst_i,
    input [2:0] profiles_i,
    input [44:0] stimulus_i,
    input [7:0] bus_read_data_i,
    input [4:0] if_reg_i,
    input [4:0] ie_reg_i,
    input [4:0] irq_pending_i,
    output [161:0] output__
);
    \iceboy::sim::soc_rom_top::soc_rom_top  impl (
        .clk_i(clk_i),
        .rst_i(rst_i),
        .profiles_i(profiles_i),
        .stimulus_i(stimulus_i),
        .bus_read_data_i(bus_read_data_i),
        .if_reg_i(if_reg_i),
        .ie_reg_i(ie_reg_i),
        .irq_pending_i(irq_pending_i),
        .output__(output__)
    );
endmodule
