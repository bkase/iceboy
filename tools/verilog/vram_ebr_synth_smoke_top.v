module vram_ebr_synth_smoke_top(
    input wire clk,
    input wire [12:0] cpu_addr_i,
    input wire [12:0] ppu_addr_i,
    input wire [12:0] dma_addr_i,
    input wire ppu_read_active_i,
    input wire dma_read_active_i,
    input wire write_en_i,
    input wire [12:0] write_addr_i,
    input wire [7:0] write_data_i,
    output wire [7:0] data_o
);
    wire [7:0] output__;

    \iceboy::mem::phys::ebr_test_top::vram_ebr_synth_test_top  dut (
        .clk_i(clk),
        .cpu_addr_i_i(cpu_addr_i),
        .ppu_addr_i_i(ppu_addr_i),
        .dma_addr_i_i(dma_addr_i),
        .ppu_read_active_i_i(ppu_read_active_i),
        .dma_read_active_i_i(dma_read_active_i),
        .write_en_i_i(write_en_i),
        .write_addr_i_i(write_addr_i),
        .write_data_i_i(write_data_i),
        .output__(output__)
    );

    assign data_o = output__;
endmodule
