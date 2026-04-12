module icebreaker_alu_loop_top_verilator_wrapper (
    input CLK,
    input BTN_N,
    input BTN_D_UP,
    input BTN_D_DOWN,
    input BTN_D_LEFT,
    input BTN_D_RIGHT,
    input DIP_A,
    input DIP_B,
    input DIP_START,
    input DIP_SELECT,
    output [226:0] output__
);
    wire ledr_n;
    wire ledg_n;
    wire lcd_sck;
    wire lcd_mosi;
    wire lcd_cs;
    wire lcd_dc;
    wire lcd_res;
    wire lcd_bl;
    wire debug_gpio0;
    wire debug_gpio1;
    wire dbg_pc0;
    wire dbg_pc1;
    wire dbg_pc2;
    wire dbg_pc3;
    wire dbg_mce;
    wire dbg_phase0;
    wire dbg_phase1;
    wire dbg_phase2;

    icebreaker_alu_loop_top impl (
        .CLK(CLK),
        .BTN_N(BTN_N),
        .BTN_D_UP(BTN_D_UP),
        .BTN_D_DOWN(BTN_D_DOWN),
        .BTN_D_LEFT(BTN_D_LEFT),
        .BTN_D_RIGHT(BTN_D_RIGHT),
        .DIP_A(DIP_A),
        .DIP_B(DIP_B),
        .DIP_START(DIP_START),
        .DIP_SELECT(DIP_SELECT),
        .LEDR_N(ledr_n),
        .LEDG_N(ledg_n),
        .LCD_SCK(lcd_sck),
        .LCD_MOSI(lcd_mosi),
        .LCD_CS(lcd_cs),
        .LCD_DC(lcd_dc),
        .LCD_RES(lcd_res),
        .LCD_BL(lcd_bl),
        .DEBUG_GPIO0(debug_gpio0),
        .DEBUG_GPIO1(debug_gpio1),
        .DBG_PC0(dbg_pc0),
        .DBG_PC1(dbg_pc1),
        .DBG_PC2(dbg_pc2),
        .DBG_PC3(dbg_pc3),
        .DBG_MCE(dbg_mce),
        .DBG_PHASE0(dbg_phase0),
        .DBG_PHASE1(dbg_phase1),
        .DBG_PHASE2(dbg_phase2)
    );

    wire [329:0] cpu = impl.alu_loop_hardware_core_0.cpu_core_0.output__;
    wire [95:0] regs = cpu[265:170];

    wire [63:0] commit_seq = cpu[329:266];
    wire [7:0] reg_a = regs[95:88];
    wire [7:0] reg_f = regs[87:80];
    wire [7:0] reg_b = regs[79:72];
    wire [7:0] reg_c = regs[71:64];
    wire [7:0] reg_d = regs[63:56];
    wire [7:0] reg_e = regs[55:48];
    wire [7:0] reg_h = regs[47:40];
    wire [7:0] reg_l = regs[39:32];
    wire [15:0] reg_sp = regs[31:16];
    wire [15:0] reg_pc = regs[15:0];
    wire [1:0] ime_state = cpu[169:168];
    wire [1:0] halt_state = cpu[167:166];
    wire [1:0] bus_req_kind = cpu[67:66];
    wire [15:0] bus_req_addr = cpu[65:50];
    wire [7:0] bus_req_data = cpu[49:42];
    wire [1:0] preview_bus_req_kind = cpu[25:24];
    wire [15:0] preview_bus_req_addr = cpu[23:8];
    wire [7:0] preview_bus_req_data = cpu[7:0];
    wire rst = 1'b0;

    // Bit layout, lsb-first:
    // [63:0] commit_seq
    // [79:64] current pc
    // [95:80] sp
    // [103:96] a
    // [111:104] f
    // [119:112] b
    // [127:120] c
    // [135:128] d
    // [143:136] e
    // [151:144] h
    // [159:152] l
    // [161:160] ime_state
    // [163:162] halt_state
    // [165:164] bus_req_kind
    // [181:166] bus_req_addr
    // [189:182] bus_req_data
    // [191:190] preview_bus_req_kind
    // [207:192] preview_bus_req_addr
    // [215:208] preview_bus_req_data
    // [216] rst
    // [217] dbg_pc0
    // [218] dbg_pc1
    // [219] dbg_pc2
    // [220] dbg_pc3
    // [221] dbg_mce
    // [222] dbg_phase0
    // [223] dbg_phase1
    // [224] dbg_phase2
    // [225] ledr_n
    // [226] ledg_n
    assign output__ = {
        ledg_n,
        ledr_n,
        dbg_phase2,
        dbg_phase1,
        dbg_phase0,
        dbg_mce,
        dbg_pc3,
        dbg_pc2,
        dbg_pc1,
        dbg_pc0,
        rst,
        preview_bus_req_data,
        preview_bus_req_addr,
        preview_bus_req_kind,
        bus_req_data,
        bus_req_addr,
        bus_req_kind,
        halt_state,
        ime_state,
        reg_l,
        reg_h,
        reg_e,
        reg_d,
        reg_c,
        reg_b,
        reg_f,
        reg_a,
        reg_sp,
        reg_pc,
        commit_seq
    };
endmodule
